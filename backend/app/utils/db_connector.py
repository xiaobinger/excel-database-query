import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import create_engine, text, pool
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError
import time
from contextlib import contextmanager
from sshtunnel import SSHTunnelForwarder
import random

# 忽略 Paramiko 的警告日志
logging.getLogger('paramiko').setLevel(logging.ERROR)
logging.getLogger('sshtunnel').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """数据库连接器，支持多种数据库类型和SSH隧道连接"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化数据库连接器
        
        Args:
            config: 数据库配置字典，包含 type, host, port, database, username, password 等
                   如果需要SSH连接，还需包含 ssh_tunnel 配置
        """
        self.config = config
        self.engine: Optional[Engine] = None
        self.connection_pool_size = config.get('pool_size', 5)
        self.max_overflow = config.get('max_overflow', 10)
        self.ssh_tunnel: Optional[SSHTunnelForwarder] = None
        self.ssh_enabled = config.get('ssh_tunnel', {}).get('enabled', False)
        self._initialize_engine()
    
    def _initialize_engine(self):
        """初始化数据库引擎"""
        db_type = self.config.get('type', 'mysql').lower()
        
        try:
            if self.ssh_enabled:
                self._setup_ssh_tunnel()
            
            logger.info(f"数据库连接配置: type={db_type}, host={self.config.get('host')}, port={self.config.get('port')}, database={self.config.get('database')}")
            
            if db_type == 'mysql':
                # 使用creator直接创建pymysql连接
                # 注意：ShardingSphere-Proxy等代理在握手阶段不接受database参数
                # 策略：先不传database连接，连接成功后USE切换
                import pymysql as _pymysql
                _cfg = dict(self.config)
                _db_name = _cfg.get('database', '')
                
                def _mysql_creator():
                    kwargs = dict(
                        host=_cfg['host'],
                        port=int(_cfg.get('port', 3306)),
                        user=_cfg['username'],
                        password=_cfg.get('password', ''),
                        charset='utf8mb4'
                    )
                    # 不传database参数，避免ShardingSphere-Proxy握手阶段报错
                    conn = _pymysql.connect(**kwargs)
                    # 连接成功后USE切换数据库
                    if _db_name:
                        try:
                            with conn.cursor() as cur:
                                cur.execute('USE `%s`' % _db_name)
                        except Exception:
                            pass  # 切换失败不影响，后续SQL会报错
                    return conn
                
                self.engine = create_engine(
                    "mysql+pymysql://",
                    creator=_mysql_creator,
                    pool_size=self.connection_pool_size,
                    max_overflow=self.max_overflow,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
            else:
                if db_type == 'postgresql':
                    connection_string = self._build_postgresql_connection_string()
                elif db_type == 'sqlite':
                    connection_string = self._build_sqlite_connection_string()
                elif db_type == 'sqlserver':
                    connection_string = self._build_sqlserver_connection_string()
                elif db_type == 'oracle':
                    connection_string = self._build_oracle_connection_string()
                else:
                    raise ValueError(f"不支持的数据库类型: {db_type}")
                
                self.engine = create_engine(
                    connection_string,
                    pool_size=self.connection_pool_size,
                    max_overflow=self.max_overflow,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
            
            logger.info(f"成功创建 {db_type} 数据库引擎{' (通过SSH隧道)' if self.ssh_enabled else ''}")
            
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}")
            if self.ssh_tunnel:
                self._close_ssh_tunnel()
            raise
    
    def _setup_ssh_tunnel(self):
        ssh_config = self.config.get('ssh_tunnel', {})
        
        ssh_host = ssh_config.get('host')
        ssh_port = int(ssh_config.get('port', 22))
        ssh_username = ssh_config.get('username')
        ssh_password = ssh_config.get('password')
        ssh_pkey_path = ssh_config.get('pkey_path')
        db_host = self.config.get('host')
        db_port = int(self.config.get('port', 3306))
        
        if not all([ssh_host, ssh_username]):
            raise ValueError("SSH隧道配置不完整，需要 host 和 username")
        
        if not ssh_password and not ssh_pkey_path:
            raise ValueError("SSH隧道需要配置 password 或 pkey_path")
        
        local_bind_port = ssh_config.get('local_bind_port') or self._get_available_local_port()
        
        try:
            tunnel_kwargs = {
                'ssh_address_or_host': (ssh_host, ssh_port),
                'ssh_username': ssh_username,
                'remote_bind_address': (db_host, db_port),
                'local_bind_address': ('127.0.0.1', local_bind_port)
            }
            if ssh_password:
                tunnel_kwargs['ssh_password'] = ssh_password
            if ssh_pkey_path:
                tunnel_kwargs['ssh_pkey'] = ssh_pkey_path
            self.ssh_tunnel = SSHTunnelForwarder(**tunnel_kwargs)
            self.ssh_tunnel.start()
            logger.info(f"SSH隧道已建立: {ssh_host}:{ssh_port} -> 127.0.0.1:{local_bind_port}")
            
            self.config['host'] = '127.0.0.1'
            self.config['port'] = local_bind_port
            
        except Exception as e:
            logger.error(f"SSH隧道建立失败: {str(e)}")
            raise
    
    def _get_available_local_port(self) -> int:
        return DatabaseConnector._get_available_local_port_static()

    @staticmethod
    def _get_available_local_port_static() -> int:
        import socket
        while True:
            port = random.randint(10000, 65535)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('127.0.0.1', port))
                sock.close()
                return port
            except OSError:
                continue
    
    def _close_ssh_tunnel(self):
        """关闭SSH隧道"""
        if self.ssh_tunnel:
            try:
                self.ssh_tunnel.stop()
                logger.info("SSH隧道已关闭")
            except Exception as e:
                logger.error(f"关闭SSH隧道时出错: {str(e)}")
            finally:
                self.ssh_tunnel = None
    
    def _build_mysql_connection_string(self) -> str:
        """构建 MySQL 连接字符串，使用 URL.create 避免 special characters 导致解析错误"""
        url = URL.create(
            drivername="mysql+pymysql",
            username=self.config['username'],
            password=self.config['password'],
            host=self.config['host'],
            port=int(self.config.get('port', 3306)),
            database=self.config['database'],
            query={"charset": "utf8mb4"}
        )
        return str(url)
    
    def _build_postgresql_connection_string(self) -> str:
        """构建 PostgreSQL 连接字符串"""
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=self.config['username'],
            password=self.config['password'],
            host=self.config['host'],
            port=int(self.config.get('port', 5432)),
            database=self.config['database']
        )
        return str(url)
    
    def _build_sqlite_connection_string(self) -> str:
        """构建 SQLite 连接字符串"""
        db_path = self.config.get('database', 'database.db')
        return f"sqlite:///{db_path}"
    
    def _build_sqlserver_connection_string(self) -> str:
        """构建 SQL Server 连接字符串"""
        driver = self.config.get('driver', 'ODBC Driver 17 for SQL Server')
        url = URL.create(
            drivername="mssql+pyodbc",
            username=self.config['username'],
            password=self.config['password'],
            host=self.config['host'],
            port=int(self.config.get('port', 1433)),
            database=self.config['database'],
            query={"driver": driver}
        )
        return str(url)
    
    def _build_oracle_connection_string(self) -> str:
        """构建 Oracle 连接字符串"""
        url = URL.create(
            drivername="oracle+cx_oracle",
            username=self.config['username'],
            password=self.config['password'],
            host=self.config['host'],
            port=int(self.config.get('port', 1521)),
            query={"service_name": self.config['database']}
        )
        return str(url)
    
    @contextmanager
    def get_connection(self):
        if not self.engine:
            raise RuntimeError("数据库引擎未初始化")
        connection = self.engine.connect()
        try:
            yield connection
        finally:
            connection.close()
    
    def _is_connection_error(self, error: Exception) -> bool:
        """判断是否为连接类错误（需要重建连接）"""
        error_str = str(error).lower()
        connection_keywords = [
            'lost connection', 'connection', 'connect', 'timed out', 'timeout',
            'broken pipe', 'gone away', 'no connection', 'not connected',
            'connection pool', 'pool exhausted', 'cannot connect',
            'refused', 'unreachable', 'reset by peer', 'network',
            'ssh tunnel', 'tunnel', '2006',  # MySQL server has gone away
            '2003',  # Can't connect to MySQL server
            '2013',  # Lost connection during query
            '08001',  # SQL Server connection error
            '08003',  # SQL Server connection not open
            '08004',  # SQL Server connection rejected
            '08006',  # SQL Server connection failure
            '08007',  # SQL Server transaction state unknown
        ]
        return any(kw in error_str for kw in connection_keywords)
    
    def _reconnect(self):
        """重建数据库引擎和SSH隧道，并同步更新连接池缓存"""
        logger.warning(f'数据库连接器: 正在重建连接 [{self.config.get("host")}:{self.config.get("port")}]...')
        try:
            if self.engine:
                self.engine.dispose()
                self.engine = None
        except Exception:
            pass
        
        try:
            if self.ssh_tunnel:
                self._close_ssh_tunnel()
        except Exception:
            pass
        
        # 重建engine和SSH隧道
        self._initialize_engine()
        logger.info('数据库连接器: 连接重建完成')
        
        # 同步更新连接池缓存中的connector引用
        try:
            from app.utils.connection_pool import ConnectionPoolManager
            pool = ConnectionPoolManager.get_instance()
            # 从config中获取conn_id（如果有的话）
            conn_id = self.config.get('conn_id')
            if conn_id:
                with pool._connector_lock:
                    pool._connectors[conn_id] = self
                logger.info(f'数据库连接器: 已同步更新连接池缓存 [ID={conn_id}]')
        except Exception as sync_err:
            logger.warning(f'数据库连接器: 同步连接池缓存失败: {sync_err}')
    
    def execute_query(self, sql: str, params: Dict[str, Any], 
                   timeout: int = 30, max_rows: int = 0, chunk_size: int = 5000) -> List[Tuple]:
        if not self.engine:
            raise RuntimeError("数据库引擎未初始化")
        
        start_time = time.time()
        
        try:
            with self.get_connection() as conn:
                result = conn.execute(text(sql), params)
                
                all_rows = []
                while True:
                    if max_rows > 0:
                        remaining = max_rows - len(all_rows)
                        if remaining <= 0:
                            break
                        batch = result.fetchmany(min(chunk_size, remaining))
                    else:
                        batch = result.fetchmany(chunk_size)
                    
                    if not batch:
                        break
                    all_rows.extend(batch)
                    
                    if max_rows > 0 and len(all_rows) >= max_rows:
                        break
                
                execution_time = time.time() - start_time
                
                complete_sql = sql
                for key, value in params.items():
                    complete_sql = complete_sql.replace(f':{key}', f"'{value}'" if isinstance(value, str) else str(value))
                
                logger.info(f"查询执行成功，返回 {len(all_rows)} 行，耗时 {execution_time:.3f} 秒")
                return all_rows
                
        except SQLAlchemyError as e:
            # 连接类错误：重建连接后重试一次
            if self._is_connection_error(e):
                logger.warning(f'查询遇到连接错误: {e}，正在重建连接重试...')
                try:
                    self._reconnect()
                    with self.get_connection() as conn:
                        result = conn.execute(text(sql), params)
                        all_rows = []
                        while True:
                            if max_rows > 0:
                                remaining = max_rows - len(all_rows)
                                if remaining <= 0:
                                    break
                                batch = result.fetchmany(min(chunk_size, remaining))
                            else:
                                batch = result.fetchmany(chunk_size)
                            if not batch:
                                break
                            all_rows.extend(batch)
                            if max_rows > 0 and len(all_rows) >= max_rows:
                                break
                        logger.info(f"重建连接后查询成功，返回 {len(all_rows)} 行")
                        return all_rows
                except Exception as retry_err:
                    logger.error(f"重建连接后重试仍然失败: {retry_err}")
                    raise retry_err
            
            execution_time = time.time() - start_time
            complete_sql = sql
            for key, value in params.items():
                complete_sql = complete_sql.replace(f':{key}', f"'{value}'" if isinstance(value, str) else str(value))
            logger.error(f"查询执行失败: {str(e)}，耗时 {execution_time:.3f} 秒")
            raise
        
        except Exception as e:
            # 连接类错误：重建连接后重试一次
            if self._is_connection_error(e):
                logger.warning(f'查询遇到连接错误: {e}，正在重建连接重试...')
                try:
                    self._reconnect()
                    with self.get_connection() as conn:
                        result = conn.execute(text(sql), params)
                        all_rows = []
                        while True:
                            if max_rows > 0:
                                remaining = max_rows - len(all_rows)
                                if remaining <= 0:
                                    break
                                batch = result.fetchmany(min(chunk_size, remaining))
                            else:
                                batch = result.fetchmany(chunk_size)
                            if not batch:
                                break
                            all_rows.extend(batch)
                            if max_rows > 0 and len(all_rows) >= max_rows:
                                break
                        logger.info(f"重建连接后查询成功，返回 {len(all_rows)} 行")
                        return all_rows
                except Exception as retry_err:
                    logger.error(f"重建连接后重试仍然失败: {retry_err}")
                    raise retry_err
            
            execution_time = time.time() - start_time
            complete_sql = sql
            for key, value in params.items():
                complete_sql = complete_sql.replace(f':{key}', f"'{value}'" if isinstance(value, str) else str(value))
            logger.error(f"未知错误: {str(e)}，耗时 {execution_time:.3f} 秒")
            raise
    
    def execute_batch_queries(self, sql: str, params_list: List[Dict[str, Any]],
                          timeout: int = 30, batch_size: int = 100, max_rows: int = 0) -> Dict[str, Any]:
        total_queries = len(params_list)
        success_count = 0
        failure_count = 0
        all_results = []
        errors = []
        total_rows_fetched = 0
        
        logger.info(f"开始批量查询，共 {total_queries} 条，批大小 {batch_size}")
        
        for i in range(0, total_queries, batch_size):
            batch = params_list[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_queries + batch_size - 1) // batch_size
            
            logger.info(f"处理批次 {batch_num}/{total_batches}，包含 {len(batch)} 条查询")
            
            for params in batch:
                try:
                    remaining = max_rows - total_rows_fetched if max_rows > 0 else 0
                    if max_rows > 0 and remaining <= 0:
                        break
                    
                    result = self.execute_query(sql, params, timeout, max_rows=remaining if max_rows > 0 else 0)
                    all_results.append({
                        'params': params,
                        'result': result,
                        'success': True
                    })
                    success_count += 1
                    total_rows_fetched += len(result)
                    
                except Exception as e:
                    error_info = {
                        'params': params,
                        'error': str(e),
                        'success': False
                    }
                    all_results.append(error_info)
                    errors.append(error_info)
                    failure_count += 1
                    logger.error(f"查询失败: {params} - {str(e)}")
            
            if max_rows > 0 and total_rows_fetched >= max_rows:
                logger.info(f"已达到最大行数限制 {max_rows}，停止查询")
                break
        
        summary = {
            'total': total_queries,
            'success': success_count,
            'failure': failure_count,
            'results': all_results,
            'errors': errors
        }
        
        logger.info(f"批量查询完成: 成功 {success_count}，失败 {failure_count}，总行数 {total_rows_fetched}")
        return summary
    
    def execute_in_query(self, sql: str, params_list: List[Dict[str, Any]],
                       timeout: int = 30, max_rows: int = 0, chunk_size: int = 5000) -> Dict[str, Any]:
        if not self.engine:
            raise RuntimeError("数据库引擎未初始化")
        
        if not params_list:
            return {
                'results': [],
                'success': 0,
                'failure': 0,
                'errors': []
            }
        
        start_time = time.time()
        
        try:
            result = self._do_execute_in_query(sql, params_list, max_rows, chunk_size)
            execution_time = time.time() - start_time
            logger.info(f"IN 查询执行成功，耗时 {execution_time:.3f} 秒")
            return result
                
        except SQLAlchemyError as e:
            # 连接类错误：重建连接后重试一次
            if self._is_connection_error(e):
                logger.warning(f'IN查询遇到连接错误: {e}，正在重建连接重试...')
                try:
                    self._reconnect()
                    return self._do_execute_in_query(sql, params_list, max_rows, chunk_size)
                except Exception as retry_err:
                    logger.error(f"重建连接后重试仍然失败: {retry_err}")
                    raise retry_err
            execution_time = time.time() - start_time
            logger.error(f"IN 查询执行失败: {str(e)}，耗时 {execution_time:.3f} 秒")
            raise
        except Exception as e:
            if self._is_connection_error(e):
                logger.warning(f'IN查询遇到连接错误: {e}，正在重建连接重试...')
                try:
                    self._reconnect()
                    return self._do_execute_in_query(sql, params_list, max_rows, chunk_size)
                except Exception as retry_err:
                    logger.error(f"重建连接后重试仍然失败: {retry_err}")
                    raise retry_err
            execution_time = time.time() - start_time
            logger.error(f"IN 查询未知错误: {str(e)}，耗时 {execution_time:.3f} 秒")
            raise
    
    def _do_execute_in_query(self, sql: str, params_list: List[Dict[str, Any]],
                       max_rows: int = 0, chunk_size: int = 5000) -> Dict[str, Any]:
        """IN查询的实际执行逻辑（供重试调用）"""
        import re
        bind_matches = re.findall(r':(\w+)', sql)
        bind_param = bind_matches[0] if bind_matches else 'value'
        
        param_values = []
        for params in params_list:
            for v in params.values():
                param_values.append(str(v))
                break
        
        in_chunk_size = 500
        all_rows = []
        total_param_count = len(param_values)
        
        with self.get_connection() as conn:
            for chunk_start in range(0, total_param_count, in_chunk_size):
                chunk_values = param_values[chunk_start:chunk_start + in_chunk_size]
                escaped_values = [v.replace("'", "''") for v in chunk_values]
                in_clause = f"({', '.join([f"'{v}'" for v in escaped_values])})"
                
                modified_sql = re.sub(rf':{bind_param}\b', in_clause, sql, flags=re.IGNORECASE)
                result = conn.execute(text(modified_sql))
                
                while True:
                    if max_rows > 0:
                        remaining = max_rows - len(all_rows)
                        if remaining <= 0:
                            break
                        batch = result.fetchmany(min(chunk_size, remaining))
                    else:
                        batch = result.fetchmany(chunk_size)
                    if not batch:
                        break
                    all_rows.extend(batch)
                    if max_rows > 0 and len(all_rows) >= max_rows:
                        break
                
                if max_rows > 0 and len(all_rows) >= max_rows:
                    break
        
        logger.info(f"IN 查询执行成功，返回 {len(all_rows)} 行")
        return {
            'results': [{
                'params': {bind_param: param_values},
                'result': all_rows,
                'success': True
            }],
            'success': 1,
            'failure': 0,
            'errors': []
        }
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.get_connection() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        try:
            with self.get_connection() as conn:
                if self.config.get('type', 'mysql').lower() == 'mysql':
                    result = conn.execute(text(
                        f"DESCRIBE {table_name}"
                    ))
                else:
                    result = conn.execute(text(
                        f"SELECT * FROM information_schema.columns "
                        f"WHERE table_name = '{table_name}'"
                    ))
                
                columns = [row[0] for row in result.fetchall()]
                return {
                    'table_name': table_name,
                    'columns': columns,
                    'column_count': len(columns)
                }
        except Exception as e:
            logger.error(f"获取表信息失败: {str(e)}")
            return {
                'table_name': table_name,
                'columns': [],
                'column_count': 0,
                'error': str(e)
            }
    
    def close(self):
        """关闭数据库连接和SSH隧道"""
        if self.engine:
            self.engine.dispose()
            logger.info("数据库连接已关闭")
        
        if self.ssh_tunnel:
            self._close_ssh_tunnel()