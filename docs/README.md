# Excel Database Query Tool v2

基于 Web 的 Excel 数据库批量查询工具，支持上传 Excel 文件中的参数列，自动匹配预定义的 SQL 脚本，批量查询多个数据库并将结果写回 Excel。

## 项目架构

```
excel-database-query-v2/
├── backend/                    # 后端服务 (Flask)
│   ├── app/
│   │   ├── __init__.py         # 应用工厂
│   │   ├── models/             # 数据模型 (SQLAlchemy)
│   │   ├── routes/             # API 路由
│   │   ├── services/           # 业务逻辑
│   │   └── utils/              # 工具函数
│   ├── requirements.txt
│   └── run.py                  # 启动入口
├── frontend/                   # 前端 (Vue 3 / React)
├── database/
│   └── init.sql                # 数据库初始化脚本
├── docs/                       # 项目文档
├── nginx/
│   └── nginx.conf              # Nginx 配置
├── docker-compose.yml          # Docker 编排
├── Dockerfile                  # 后端镜像
├── .env.example                # 环境变量示例
└── .gitignore
```

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Element Plus | 响应式管理界面 |
| 后端 | Flask + SQLAlchemy | RESTful API 服务 |
| 数据库 | MySQL 8.0+ | 元数据存储 |
| 缓存 | Redis (可选) | 查询缓存、会话管理 |
| 部署 | Docker + Nginx | 容器化部署 |
| SSH | Paramiko / sshtunnel | SSH 隧道连接 |

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 8.0+
- Node.js 18+ (前端开发)
- Docker & Docker Compose (容器化部署)

### 方式一：本地开发

#### 1. 克隆项目

```bash
git clone <repository-url>
cd excel-database-query-v2
```

#### 2. 初始化数据库

```bash
# 登录 MySQL
mysql -u root -p

# 创建数据库
CREATE DATABASE excel_query_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 导入初始化脚本
USE excel_query_db;
SOURCE database/init.sql;
```

#### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入实际配置
```

#### 4. 启动后端

```bash
cd backend
pip install -r requirements.txt
python run.py
```

后端默认运行在 `http://localhost:5000`

#### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`

### 方式二：Docker 部署

```bash
# 一键启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

服务启动后：
- 前端：`http://localhost`
- 后端 API：`http://localhost/api`
- MySQL：`localhost:3306`

## API 文档

### 认证接口

#### POST /api/auth/login

用户登录，获取 JWT Token。

**请求体：**

```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": 1,
      "username": "admin",
      "role": "admin"
    }
  }
}
```

#### POST /api/auth/logout

用户登出，需在 Header 中携带 Token。

#### GET /api/auth/me

获取当前用户信息。

---

### 数据库连接管理

#### GET /api/connections

获取所有数据库连接列表。

**响应：**

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "rfsht_pro_db",
      "description": "融付商户通-生产环境",
      "db_type": "mysql",
      "host": "zf-rfsht.rwlb.rds.aliyuncs.com",
      "port": 3306,
      "database_name": "posp_business",
      "ssh_enabled": true,
      "is_active": true,
      "created_at": "2026-05-28T10:00:00"
    }
  ]
}
```

#### POST /api/connections

创建新的数据库连接。

**请求体：**

```json
{
  "name": "my_db",
  "description": "我的数据库",
  "db_type": "mysql",
  "host": "localhost",
  "port": 3306,
  "database_name": "my_database",
  "username": "root",
  "password": "password123",
  "ssh_enabled": false,
  "pool_size": 5,
  "max_overflow": 10
}
```

#### PUT /api/connections/{id}

更新数据库连接配置。

#### DELETE /api/connections/{id}

删除数据库连接（软删除，设置 is_active=false）。

#### POST /api/connections/{id}/test

测试数据库连接是否可用。

**响应：**

```json
{
  "success": true,
  "data": {
    "connected": true,
    "version": "8.0.32",
    "latency_ms": 45
  }
}
```

---

### SQL 脚本管理

#### GET /api/scripts

获取所有 SQL 脚本列表。

**响应：**

```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "user_basic_info_rfsht",
      "tag": "融付商户通-商户信息",
      "description": "匹配融付商户通商户信息",
      "db_connection_ids": [1],
      "batch_size": 100,
      "timeout": 30,
      "result_sheet_name": "用户基本信息",
      "is_active": true
    }
  ]
}
```

#### POST /api/scripts

创建新的 SQL 脚本。

**请求体：**

```json
{
  "name": "my_query",
  "tag": "我的查询",
  "description": "查询描述",
  "sql_content": "SELECT * FROM users WHERE id IN :value",
  "db_connection_ids": [1, 2],
  "batch_size": 100,
  "timeout": 30,
  "result_sheet_name": "查询结果",
  "date_format": "%Y-%m-%d %H:%M:%S"
}
```

#### PUT /api/scripts/{id}

更新 SQL 脚本。

#### DELETE /api/scripts/{id}

删除 SQL 脚本。

#### POST /api/scripts/{id}/validate

验证 SQL 脚本语法和安全性。

**响应：**

```json
{
  "success": true,
  "data": {
    "valid": true,
    "warnings": [],
    "has_parameter": true
  }
}
```

---

### 查询任务

#### POST /api/tasks

创建查询任务（上传 Excel 并执行查询）。

**请求：** `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | Excel 文件 (.xlsx/.xls) |
| column_name | String | 否 | 参数列名，默认第一列 |
| script_ids | String | 是 | 脚本ID数组，JSON格式如 "[1,2,3]" |
| new_sheet | Boolean | 否 | 是否新建工作表，默认 true |

**响应：**

```json
{
  "success": true,
  "data": {
    "task_id": "TASK_20260528_001",
    "status": "pending",
    "message": "任务已创建，等待执行"
  }
}
```

#### GET /api/tasks

获取任务列表（支持分页和筛选）。

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码，默认 1 |
| per_page | int | 每页条数，默认 20 |
| status | string | 筛选状态: pending/running/completed/failed |

#### GET /api/tasks/{task_id}

获取任务详情。

**响应：**

```json
{
  "success": true,
  "data": {
    "task_id": "TASK_20260528_001",
    "status": "completed",
    "file_name": "商户列表.xlsx",
    "column_name": "商户编号",
    "script_ids": [1, 2],
    "progress": 100,
    "execution_time": 12,
    "result_count": 256,
    "output_file_path": "/results/result_20260528_001.xlsx",
    "started_at": "2026-05-28T10:05:00",
    "completed_at": "2026-05-28T10:05:12"
  }
}
```

#### GET /api/tasks/{task_id}/status

获取任务实时状态（轮询用）。

**响应：**

```json
{
  "success": true,
  "data": {
    "task_id": "TASK_20260528_001",
    "status": "running",
    "progress": 65,
    "elapsed_time": "00:00:08"
  }
}
```

#### GET /api/tasks/{task_id}/download

下载查询结果文件。

#### GET /api/tasks/{task_id}/logs

获取任务执行日志。

**响应：**

```json
{
  "success": true,
  "data": [
    {
      "level": "INFO",
      "message": "开始执行查询...",
      "created_at": "2026-05-28T10:05:00"
    },
    {
      "level": "INFO",
      "message": "连接数据库 rfsht_pro_db 成功",
      "created_at": "2026-05-28T10:05:01"
    }
  ]
}
```

#### POST /api/tasks/{task_id}/cancel

取消正在执行的任务。

---

### 用户管理

#### GET /api/users

获取用户列表（仅管理员）。

#### POST /api/users

创建新用户（仅管理员）。

#### PUT /api/users/{id}

更新用户信息。

#### PUT /api/users/{id}/password

修改用户密码。

---

### 系统接口

#### GET /api/health

健康检查。

**响应：**

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime": "3d 12h 30m"
}
```

#### GET /api/stats

系统统计信息（仅管理员）。

## 配置说明

### 环境变量 (.env)

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| FLASK_ENV | 运行环境 | development |
| FLASK_DEBUG | 调试模式 | false |
| SECRET_KEY | 应用密钥 | - |
| DATABASE_URL | 元数据库连接串 | mysql+pymysql://root:password@localhost:3306/excel_query_db |
| REDIS_URL | Redis 连接串 (可选) | redis://localhost:6379/0 |
| UPLOAD_FOLDER | 上传文件目录 | ./uploads |
| RESULT_FOLDER | 结果文件目录 | ./results |
| MAX_CONTENT_LENGTH | 最大上传大小 (MB) | 50 |
| PROD_DB_PASSWORD | 生产数据库密码 | - |
| JWT_SECRET_KEY | JWT 签名密钥 | - |
| JWT_EXPIRATION_HOURS | Token 过期时间 (小时) | 24 |
| LOG_LEVEL | 日志级别 | INFO |
| CORS_ORIGINS | 允许的跨域来源 | http://localhost:3000 |
| SSH_TUNNEL_TIMEOUT | SSH 隧道超时 (秒) | 30 |

### 数据库连接配置

数据库连接信息存储在 `db_connections` 表中，支持以下数据库类型：

- **mysql** - MySQL / MariaDB
- **postgresql** - PostgreSQL
- **sqlite** - SQLite (本地文件)
- **sqlserver** - Microsoft SQL Server
- **oracle** - Oracle Database

SSH 隧道连接支持：
- 密码认证
- 密钥认证（将密钥文件放在 `config/ssh_keys/` 目录下）

## 使用教程

### 基本工作流程

1. **登录系统** - 使用管理员账号 (admin/admin123) 登录
2. **配置数据库连接** - 在"数据库管理"页面添加目标数据库连接
3. **创建 SQL 脚本** - 在"脚本管理"页面编写查询 SQL，使用 `:value` 作为参数占位符
4. **上传 Excel** - 在"查询任务"页面上传包含查询参数的 Excel 文件
5. **选择脚本执行** - 选择要执行的 SQL 脚本，指定参数列
6. **下载结果** - 查询完成后下载包含结果的 Excel 文件

### SQL 脚本编写指南

SQL 脚本中使用 `:value` 作为参数占位符，系统会自动将 Excel 中指定列的值替换为参数：

```sql
-- 单列参数查询
SELECT * FROM users WHERE user_id IN :value

-- :value 会被替换为 (1, 2, 3, ...) 形式
```

**注意事项：**
- 只支持 `SELECT` 查询，禁止 `INSERT`/`UPDATE`/`DELETE` 等写操作
- 使用 `IN :value` 而非 `= :value`，以支持批量查询
- 大批量数据会自动分批执行（默认每批 100 条）
- 建议为查询设置合理的超时时间

### Excel 文件格式要求

- 文件格式：`.xlsx` 或 `.xls`
- 参数列：第一行为列名，后续行为数据
- 数据量：建议单次不超过 10,000 行

示例 Excel 格式：

| 商户编号 |
|----------|
| M001 |
| M002 |
| M003 |

### 多库联合查询

部分查询需要同时查询多个数据库（如终端交易情况匹配），系统会：
1. 依次连接每个数据库执行相同的 SQL
2. 将各库结果合并到同一个工作表
3. 在结果中标注数据来源

## 常见问题 FAQ

### Q: 连接数据库超时怎么办？

A: 检查以下几点：
1. 确认数据库地址和端口是否正确
2. 如果使用 SSH 隧道，确认 SSH 服务器可达
3. 检查防火墙/安全组规则
4. 增大 `timeout` 配置值

### Q: SSH 隧道连接失败？

A: 常见原因：
1. SSH 服务器未启动或端口被封锁
2. SSH 用户名/密码错误
3. 本地端口被占用（修改 `local_bind_port`）
4. SSH 服务器限制了连接数

### Q: 查询结果中中文乱码？

A: 确保数据库和表的字符集为 `utf8mb4`，连接参数中指定 `charset=utf8mb4`。

### Q: 上传的 Excel 文件大小限制？

A: 默认限制 50MB，可通过 `MAX_CONTENT_LENGTH` 环境变量调整。

### Q: 如何修改默认管理员密码？

A: 登录后在"个人设置"中修改，或通过 API `PUT /api/users/1/password` 修改。

### Q: 查询任务一直处于 running 状态？

A: 可能原因：
1. 数据库查询耗时过长，检查 SQL 是否需要优化
2. 后端进程异常退出，重启服务
3. 调用 `POST /api/tasks/{task_id}/cancel` 取消任务

## 开发指南

### 添加新的数据库类型支持

1. 在 `backend/app/services/database_connector.py` 中添加新的连接器类
2. 继承 `BaseConnector` 基类，实现 `connect()`、`execute()`、`close()` 方法
3. 在 `db_connections.db_type` 的 ENUM 中添加新类型
4. 更新前端数据库类型选择器

### 添加新的查询功能

1. 在 `backend/app/routes/` 中创建新的路由文件
2. 在 `backend/app/services/` 中实现业务逻辑
3. 在 `backend/app/__init__.py` 中注册蓝图
4. 更新前端对应页面

### 项目结构约定

- **路由层** (`routes/`) - 只负责请求解析和响应格式化
- **服务层** (`services/`) - 核心业务逻辑，可被多个路由复用
- **模型层** (`models/`) - 数据库模型定义，与表结构一一对应
- **工具层** (`utils/`) - 通用工具函数

### 代码规范

- Python 代码遵循 PEP 8
- 使用 type hints 标注函数签名
- API 响应统一格式：`{"success": bool, "data": ..., "error": ...}`
- 错误码规范：4xx 客户端错误，5xx 服务端错误

### 运行测试

```bash
cd backend
pytest tests/ -v --cov=app
```

## 许可证

内部项目，仅供团队使用。
