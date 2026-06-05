# Excel Database Query - Excel数据库查询系统

基于 Flask + Vue3 的企业级数据库查询与导出平台，支持多数据库连接、SSH隧道、智能匹配、SQL模板、自动导出、AI辅助等功能。

## 功能概览

### 核心功能
- **查询执行**：上传Excel文件，选择查询选项，自动执行数据库查询并将结果写回Excel
- **导出任务**：基于导出选项配置参数，直接从数据库导出数据到Excel
- **自动导出**：Cron定时触发导出任务，支持邮件通知
- **SQL模板**：Jinja2语法动态生成SQL，支持按月分表UNION ALL等场景
- **智能匹配**：根据上传文件名自动推荐查询选项，支持直通模式（自动执行+下载）

### 数据库支持
- MySQL / MariaDB（pymysql）
- PostgreSQL（psycopg2）
- SQL Server（pyodbc）
- SSH隧道连接（paramiko + sshtunnel）

### 权限体系
- RBAC角色权限（菜单权限 + 按钮权限）
- 用户授权查询选项/导出选项/自动任务
- 超级管理员/管理员查看所有数据，普通用户仅看自己的

### AI功能
- AI模型配置（OpenAI兼容API）
- 用户行为追踪与自主学习
- AI技能管理（系统/用户/自动学习）
- AI对话（Markdown渲染）

### 其他
- 5套主题切换（默认蓝、粉色甜美、阳光橙色、暗黑、豆绿养眼）
- 性别自动主题匹配
- 列名同义词模糊匹配
- 文件定时清理
- SSE实时状态推送
- 大数据量分批执行

## 项目结构

```
excel-database-query/
├── backend/                    # Flask后端
│   ├── app/
│   │   ├── __init__.py        # 应用工厂、数据库初始化、蓝图注册
│   │   ├── config.py          # YAML配置加载
│   │   ├── models/            # 数据模型
│   │   │   ├── database.py    # 数据库连接
│   │   │   ├── script.py      # 查询/导出选项（含SQL模板字段）
│   │   │   ├── query_task.py  # 查询/导出任务
│   │   │   ├── ssh_config.py  # SSH配置
│   │   │   ├── user.py        # 用户
│   │   │   ├── role.py        # 角色
│   │   │   ├── system_config.py # 系统配置（邮件/同义词/AI）
│   │   │   ├── auto_export_task.py # 自动导出任务
│   │   │   ├── ai_config.py   # AI模型配置
│   │   │   ├── ai_skill.py    # AI技能
│   │   │   ├── ai_chat.py     # AI对话
│   │   │   └── user_behavior.py # 用户行为
│   │   ├── routes/            # API路由
│   │   │   ├── auth_routes.py     # 认证（登录/滑块验证）
│   │   │   ├── database_routes.py # 数据库连接管理
│   │   │   ├── script_routes.py   # 查询/导出选项CRUD + 模板渲染
│   │   │   ├── query_routes.py    # 查询执行 + 智能匹配
│   │   │   ├── export_routes.py   # 导出执行
│   │   │   ├── auto_export_routes.py # 自动导出管理
│   │   │   ├── download_routes.py # 文件下载
│   │   │   ├── user_routes.py     # 用户管理
│   │   │   ├── role_routes.py     # 角色管理
│   │   │   ├── system_routes.py   # 系统配置
│   │   │   ├── ssh_routes.py      # SSH配置
│   │   │   └── ai_routes.py       # AI配置/技能/对话
│   │   ├── services/          # 业务服务
│   │   │   ├── query_service.py       # 查询执行引擎
│   │   │   ├── export_service.py      # 导出执行引擎
│   │   │   ├── auto_export_scheduler.py # 自动导出调度器
│   │   │   ├── excel_service.py       # Excel读写
│   │   │   ├── database_service.py    # 数据库连接服务
│   │   │   ├── ssh_service.py         # SSH隧道服务
│   │   │   └── ai_service.py          # AI服务
│   │   └── utils/             # 工具类
│   │       ├── sql_validator.py   # SQL验证/格式化/列名提取
│   │       ├── sql_template.py    # SQL模板渲染引擎（Jinja2）
│   │       ├── db_connector.py    # 数据库连接器
│   │       ├── excel_reader.py    # Excel读取
│   │       ├── excel_writer.py    # Excel写入
│   │       ├── auth.py            # JWT认证/权限装饰器
│   │       ├── behavior_tracker.py # 用户行为追踪
│   │       ├── helpers.py         # 工具函数（时区等）
│   │       └── file_cleanup.py    # 文件定时清理
│   ├── config.yaml            # 应用配置
│   ├── requirements.txt       # Python依赖
│   ├── run.py                 # 启动入口
│   └── seed_data.py           # 初始化数据
├── frontend/                   # Vue3前端
│   ├── src/
│   │   ├── api/index.js       # API接口
│   │   ├── components/        # 公共组件
│   │   │   ├── Layout.vue     # 布局框架
│   │   │   ├── SqlEditor.vue  # SQL编辑器（高亮+补全）
│   │   │   └── ThemeSwitch.vue # 主题切换
│   │   ├── views/             # 页面
│   │   │   ├── Login.vue          # 登录
│   │   │   ├── Dashboard.vue      # 仪表盘
│   │   │   ├── QueryExecutor.vue   # 查询执行
│   │   │   ├── ScriptManager.vue   # 查询选项管理
│   │   │   ├── ExportExecutor.vue  # 导出执行
│   │   │   ├── ExportManager.vue   # 导出选项管理
│   │   │   ├── AutoExportManager.vue # 自动导出管理
│   │   │   ├── DatabaseManager.vue  # 数据库管理
│   │   │   ├── History.vue         # 执行历史
│   │   │   ├── UserManager.vue     # 用户管理
│   │   │   ├── RoleManager.vue     # 角色管理
│   │   │   ├── SystemConfig.vue    # 系统配置
│   │   │   ├── AiChat.vue          # AI对话
│   │   │   └── SkillManager.vue    # 技能管理
│   │   ├── stores/index.js    # Pinia状态管理
│   │   ├── router/index.js    # 路由
│   │   └── styles/            # 样式（主题等）
│   └── package.json
└── .trae/                      # Trae配置
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+

### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 修改配置
# 编辑 config.yaml，配置数据库连接、密钥等

# 启动服务
python run.py
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 默认账号
- 超级管理员：`admin` / `admin123`

## 配置说明

### config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 5000
  debug: true

database:
  host: "localhost"
  port: 3306
  name: "excel_query_db"
  username: "root"
  password: "123456"
  charset: "utf8mb4"

security:
  secret_key: "your-secret-key"
  jwt_secret_key: "your-jwt-secret-key"
  encryption_key: "your-encryption-key-32-bytes-long!"

storage:
  upload_folder: "./uploads"
  output_folder: "./outputs"
  log_folder: "./logs"
  max_content_length_mb: 50
  file_retention_hours: 24

smart_match:
  enabled: true
  direct: false          # true时匹配到直接执行并下载，不弹窗确认
  rules:
      #匹配上传文件名中的关键词
    - filename_keywords: [""]
      # 匹配的查询选项标签
      script_tags: [""]
      # 默认参数列名
      default_param_column: [""]
```

## SQL模板功能

查询选项和导出选项支持SQL模板模式，使用Jinja2语法动态生成SQL。

### 使用场景

按月分表的场景，需要查询最近12个月的数据并UNION ALL：

```jinja2
{% for m in months %}
SELECT * FROM transaction_{{ m }}
WHERE merchant_id = :value
{% if not loop.last %} UNION ALL {% endif %}
{% endfor %}
```

### 模板变量类型

| 类型 | 说明 | 配置项 |
|------|------|--------|
| `date_range` | 生成日期列表 | period(month/year/day), count, direction(past/future), format, offset |
| `date` | 日期参数 | default(today/now/yesterday/first_day_of_month/last_day_of_month), format |
| `text` | 文本参数 | default |
| `number` | 数字参数 | default |

### date_range 示例

配置变量名 `months`，类型 `date_range`：
- period: `month`，count: `12`，direction: `past`，format: `%Y%m`
- 渲染结果：`months = ['202506', '202505', '202504', ..., '202407']`

## API概览

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | `/api/auth/*` | 登录、验证码 |
| 数据库 | `/api/databases/*` | 数据库连接CRUD、测试连接 |
| SSH | `/api/ssh/*` | SSH配置CRUD |
| 查询选项 | `/api/scripts/*` | 查询/导出选项CRUD、模板渲染 |
| 查询执行 | `/api/query/*` | 查询执行、智能匹配、SSE状态 |
| 导出执行 | `/api/export/*` | 导出执行 |
| 自动导出 | `/api/auto-export/*` | 自动导出任务CRUD |
| 下载 | `/api/download/*` | 结果文件下载 |
| 用户 | `/api/users/*` | 用户CRUD |
| 角色 | `/api/roles/*` | 角色CRUD、权限分配 |
| 系统配置 | `/api/system/*` | 邮件/同义词/AI配置 |
| AI | `/api/ai/*` | AI模型、技能、对话 |

## 技术栈

**后端**：Flask + SQLAlchemy + PyJWT + Jinja2 + openpyxl + sshtunnel + croniter

**前端**：Vue3 + Vite + Element Plus + Pinia + Vue Router + marked + highlight.js

**数据库**：SQLite（应用库）+ MySQL/PostgreSQL/SQLServer（业务库）
