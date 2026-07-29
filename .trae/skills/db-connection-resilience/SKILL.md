---
name: "db-connection-resilience"
description: "Implement resilient database connection with auto-reconnect, health checks, and pool recycling. Invoke when database connections drop, timeout, or need reliability improvements in Python/SQLAlchemy projects."
---

# 数据库连接韧性保障指南

Python 后端长期运行时数据库连接失效是高频问题，需要多层防护。本指南提炼自多次踩坑实践，适用于任何 SQLAlchemy + Flask 项目。

## 问题根因

长时间运行的服务中，数据库连接会因以下原因失效：
- MySQL `wait_timeout` 默认8小时断开空闲连接
- 网络抖动/中间件重置导致连接丢失
- SSH 隧道超时断开
- 连接池中的连接过期但未检测

## 三层防护架构

```
请求 → [连接池健康检查] → [连接器重试] → [引擎保活参数]
```

### 第1层：引擎保活参数

在 `create_engine()` 时配置关键参数：

```python
from sqlalchemy import create_engine

# MySQL 连接
engine = create_engine(
    "mysql+pymysql://...",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,        # 每次从池取连接前先ping，无效连接自动丢弃
    pool_recycle=1800,          # 30分钟强制回收连接（必须小于MySQL wait_timeout）
    echo=False
)

# MySQL 使用 creator 方式时，加保活参数
import pymysql

def mysql_creator():
    conn = pymysql.connect(
        host=config['host'],
        port=config['port'],
        user=config['username'],
        password=config['password'],
        charset='utf8mb4',
        read_timeout=60,        # 读超时60秒
        write_timeout=60,       # 写超时60秒
    )
    return conn

engine = create_engine(
    "mysql+pymysql://",
    creator=mysql_creator,
    pool_pre_ping=True,
    pool_recycle=1800,
)
```

**关键参数说明**:
- `pool_pre_ping=True`: SQLAlchemy 内置机制，每次获取连接前发送轻量检测，失败自动换新连接
- `pool_recycle=1800`: 每30分钟强制回收，确保不超过 MySQL `wait_timeout`（默认8小时=28800秒）
- `read_timeout/write_timeout=60`: MySQL 驱动层保活，防止查询无限等待

### 第2层：连接器重试机制

`get_connection()` 方法内置重试，连接失败自动重建：

```python
from contextlib import contextmanager

MAX_RECONNECT_RETRIES = 2  # 最大重试次数

@contextmanager
def get_connection(self):
    """获取数据库连接，自动重试连接失败"""
    if not self.engine:
        raise RuntimeError("数据库引擎未初始化")

    last_error = None
    for attempt in range(MAX_RECONNECT_RETRIES + 1):
        try:
            connection = self.engine.connect()
            try:
                yield connection
                return
            finally:
                connection.close()
        except Exception as e:
            last_error = e
            if self._is_connection_error(e) and attempt < MAX_RECONNECT_RETRIES:
                logger.warning(f'获取连接失败(第{attempt+1}次): {e}，正在重建连接...')
                try:
                    self._reconnect()
                except Exception as reconnect_err:
                    logger.error(f'重建连接失败: {reconnect_err}')
            else:
                raise
    raise last_error
```

**连接类错误识别**:

```python
def _is_connection_error(self, error: Exception) -> bool:
    """判断是否为连接类错误（需要重建连接而非简单重试）"""
    error_str = str(error).lower()
    connection_keywords = [
        # 通用连接错误
        'lost connection', 'connection', 'connect', 'timed out', 'timeout',
        'broken pipe', 'gone away', 'no connection', 'not connected',
        'connection pool', 'pool exhausted', 'cannot connect',
        'refused', 'unreachable', 'reset by peer', 'network',
        # SSH隧道
        'ssh tunnel', 'tunnel',
        # MySQL错误码
        '2006',  # MySQL server has gone away
        '2003',  # Can't connect to MySQL server
        '2013',  # Lost connection during query
        # SQL Server错误码
        '08001', '08003', '08004', '08006', '08007',
    ]
    return any(kw in error_str for kw in connection_keywords)
```

**重建连接方法**:

```python
def _reconnect(self):
    """重建数据库引擎和SSH隧道，并同步更新连接池缓存"""
    logger.warning('数据库连接器: 正在重建连接...')

    # 1. 销毁旧引擎
    try:
        if self.engine:
            self.engine.dispose()
            self.engine = None
    except Exception:
        pass

    # 2. 关闭旧SSH隧道
    try:
        if self.ssh_tunnel:
            self._close_ssh_tunnel()
    except Exception:
        pass

    # 3. 重建引擎（含SSH隧道）
    self._initialize_engine()
    logger.info('数据库连接器: 连接重建完成')

    # 4. 同步更新连接池缓存中的引用（关键！）
    try:
        from app.utils.connection_pool import ConnectionPoolManager
        pool = ConnectionPoolManager.get_instance()
        conn_id = self.config.get('conn_id')
        if conn_id:
            with pool._connector_lock:
                pool._connectors[conn_id] = self
            logger.info(f'已同步更新连接池缓存 [ID={conn_id}]')
    except Exception as sync_err:
        logger.warning(f'同步连接池缓存失败: {sync_err}')
```

### 第3层：连接池健康检查

在连接池管理层提供带健康检查的获取方法：

```python
def get_connector_with_health_check(self, conn_id: int):
    """获取数据库连接，带健康检查。不健康时自动重建连接。"""
    connector = self.get_connector(conn_id)
    if not connector:
        return None

    # 快速检查：engine是否存活
    if not connector.engine:
        logger.warning(f'连接 [ID={conn_id}] engine不存在，正在重建...')
        self.reload_connector(conn_id)
        return self.get_connector(conn_id)

    # 健康检查：执行 SELECT 1
    if not self._check_connector_health(connector):
        logger.warning(f'连接 [ID={conn_id}] 健康检查失败，正在重建...')
        self.reload_connector(conn_id)
        return self.get_connector(conn_id)

    return connector

def _check_connector_health(self, connector) -> bool:
    """检查连接是否健康"""
    try:
        if not connector.engine:
            return False
        from sqlalchemy import text
        with connector.get_connection() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

**服务层调用规范**（所有使用数据库的服务统一使用）：

```python
from app.utils.connection_pool import ConnectionPoolManager

pool = ConnectionPoolManager.get_instance()
# 正确 ✓
connector = pool.get_connector_with_health_check(conn_id)
# 错误 ✗ — 不会自动重建失效连接
connector = pool.get_connector(conn_id)
```

## 大数据量查询优化

### 流式结果集

避免大数据量一次性加载到内存：

```python
# 使用 server-side cursor
result = conn.execution_options(stream_results=True).execute(text(sql), params)

# 分批获取
all_rows = []
while True:
    batch = result.fetchmany(5000)  # 每批5000行
    if not batch:
        break
    all_rows.extend(batch)
    if max_rows > 0 and len(all_rows) >= max_rows:
        break
```

### 批量查询自动转IN模式

单参数SQL自动合并到IN子句，减少SQL往返：

```python
def execute_batch_queries(self, sql, params_list, ...):
    # 检测SQL绑定参数数量
    bind_matches = re.findall(r':(\w+)', sql)

    # 单参数：自动转IN模式（性能提升数十倍）
    if len(bind_matches) == 1 and len(params_list) > 1:
        return self._do_execute_in_query(sql, params_list, ...)

    # 多参数：逐条查询
    for params in params_list:
        result = self.execute_query(sql, params, ...)
```

## Model 配置同步

Model 的 `to_config_dict()` 必须包含 `conn_id`，使重建连接后能同步连接池缓存：

```python
class DatabaseConnection(db.Model):
    def to_config_dict(self):
        return {
            'conn_id': self.id,    # 关键！重连后需要同步缓存
            'type': self.db_type,
            'host': self.host,
            'port': self.port,
            # ...其他配置
        }
```

## 排错清单

当出现"数据库连接不上"时，依次检查：

1. **pool_recycle 是否够短**: 必须 < MySQL `wait_timeout`，推荐1800
2. **pool_pre_ping 是否开启**: 必须为 True
3. **MySQL 是否有保活参数**: `read_timeout`/`write_timeout` 不能为0
4. **get_connector 方法**: 是否用 `get_connector_with_health_check()` 替代了 `get_connector()`
5. **重连后缓存同步**: `_reconnect()` 是否更新了连接池缓存中的引用
6. **SSH隧道**: 长时间空闲后隧道是否断开，重连时是否重建了隧道
7. **错误识别范围**: `_is_connection_error()` 的关键字列表是否覆盖了实际遇到的错误
