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
- **AI模型Logo自动适配**：内置15+主流供应商Logo（OpenAI、Anthropic、Google、Azure、DeepSeek、Moonshot、Zhipu、百度、阿里、腾讯、商汤、OpenRouter、Poolside、Nemotron、ox-alpha），未匹配品牌自动通过DuckDuckGo Favicon服务获取远程Logo
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
│   │   │   │   ├── ai_config.py   # AI模型配置（含logo_url）
│   │   │   │   ├── ai_skill.py    # AI技能
│   │   │   │   ├── ai_chat.py     # AI对话
│   │   │   │   ├── ai_agent.py   # AI Agent
│   │   │   │   ├── ai_strategy.py # AI策略
│   │   │   │   ├── agent_memory.py # Agent记忆
│   │   │   │   ├── api_call_log.py # 开放API调用日志（含session_id）
│   │   │   │   ├── api_key.py    # 开放API密钥
│   │   │   │   ├── auto_export_task.py # 自动导出任务
│   │   │   │   ├── business_system.py # 业务系统
│   │   │   │   ├── mcp_server.py  # MCP服务器
│   │   │   │   ├── pay_config.py  # 代付配置
│   │   │   │   ├── system_task.py # 系统任务（含响应字段映射）
│   │   │   │   ├── ticket.py      # 工单
│   │   │   │   ├── tool_memory.py # 工具记忆
│   │   │   │   └── user_behavior.py # 用户行为
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
│   │   │   ├── ai_routes.py       # AI配置/技能/对话
│   │   │   ├── agent_routes.py    # AI Agent管理
│   │   │   ├── ai_strategy_routes.py # AI策略
│   │   │   ├── api_admin_routes.py # 开放API管理（日志/统计/会话）
│   │   │   ├── auto_export_routes.py # 自动导出管理
│   │   │   ├── business_system_routes.py # 业务系统
│   │   │   ├── cache_routes.py    # 缓存管理
│   │   │   ├── download_routes.py # 文件下载
│   │   │   ├── lookup_routes.py   # 字典查询
│   │   │   ├── mcp_routes.py      # MCP服务器管理
│   │   │   ├── open_api_routes.py # 开放API（/v1/*）
│   │   │   ├── pay_routes.py      # 代付提现
│   │   │   ├── profit_share_routes.py # 分润
│   │   │   ├── system_task_routes.py # 系统任务
│   │   │   ├── task_routes.py     # 查询/导出任务
│   │   │   └── ticket_routes.py   # 工单管理
│   │   ├── services/          # 业务服务
│   │   │   ├── query_service.py       # 查询执行引擎
│   │   │   ├── export_service.py      # 导出执行引擎
│   │   │   ├── auto_export_scheduler.py # 自动导出调度器
│   │   │   ├── excel_service.py       # Excel读写
│   │   │   ├── database_service.py    # 数据库连接服务
│   │   │   ├── ssh_service.py         # SSH隧道服务
│   │   │   ├── ai_service.py          # AI服务
│   │   │   ├── lookup_service.py      # 字典查询服务
│   │   │   ├── mcp_service.py         # MCP服务
│   │   │   ├── mcp_marketplace.py     # MCP市场
│   │   │   ├── open_api_service.py    # 开放API服务
│   │   │   ├── pay_service.py         # 代付服务
│   │   │   ├── profit_share_service.py # 分润服务
│   │   │   └── system_task_service.py # 系统任务服务
│   │   └── utils/             # 工具类
│   │       ├── sql_validator.py   # SQL验证/格式化/列名提取
│   │       ├── sql_template.py    # SQL模板渲染引擎（Jinja2）
│   │       ├── db_connector.py    # 数据库连接器
│   │       ├── excel_reader.py    # Excel读取
│   │       ├── excel_writer.py    # Excel写入
│   │       ├── auth.py            # JWT认证/权限装饰器
│   │       ├── behavior_tracker.py # 用户行为追踪
│   │       ├── helpers.py         # 工具函数（时区等）
│   │       ├── file_cleanup.py    # 文件定时清理
│   │       ├── connection_pool.py # 数据库连接池
│   │       ├── error_sanitizer.py # 错误信息脱敏
│   │       ├── rate_limiter.py    # 限流
│   │       └── url_validator.py   # URL校验
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
│   │   │   ├── ThemeSwitch.vue # 主题切换
│   │   │   ├── MarkdownEditor.vue # Markdown编辑器
│   │   │   ├── ProviderLogo.vue # AI供应商Logo渲染
│   │   │   ├── TagsView.vue    # 标签视图
│   │   │   ├── TaskBadge.vue   # 任务徽章
│   │   │   └── TaskNotificationCenter.vue # 任务通知中心
│   │   ├── views/             # 页面
│   │   │   ├── Login.vue                  # 登录
│   │   │   ├── Dashboard.vue              # 仪表盘
│   │   │   ├── QueryExecutor.vue           # 查询执行
│   │   │   ├── ScriptManager.vue           # 查询选项管理
│   │   │   ├── ExportExecutor.vue          # 导出执行
│   │   │   ├── ExportManager.vue           # 导出选项管理
│   │   │   ├── AutoExportManager.vue       # 自动导出管理
│   │   │   ├── DatabaseManager.vue         # 数据库管理
│   │   │   ├── History.vue                 # 执行历史
│   │   │   ├── UserManager.vue             # 用户管理
│   │   │   ├── RoleManager.vue             # 角色管理
│   │   │   ├── SystemConfig.vue            # 系统配置
│   │   │   ├── AiChat.vue                  # AI对话
│   │   │   ├── SkillManager.vue            # 技能管理
│   │   │   ├── AgentManager.vue            # Agent管理
│   │   │   ├── ApiAdmin.vue                # 开放API管理
│   │   │   ├── BusinessSystemManager.vue   # 业务系统管理
│   │   │   ├── McpManager.vue              # MCP服务器管理
│   │   │   ├── PayManager.vue              # 代付提现
│   │   │   ├── ProfitShare.vue             # 分润管理
│   │   │   ├── SystemTaskManager.vue       # 系统任务管理
│   │   │   └── TicketManager.vue           # 工单管理
│   │   ├── stores/index.js    # Pinia状态管理
│   │   ├── router/index.js    # 路由
│   │   ├── utils/             # 工具
│   │   │   ├── providerLogo.js # Logo自动适配
│   │   │   └── sql.js         # SQL工具
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
| 开放API | `/api/open-api/*` | 开放API调用、日志、统计、会话聚合 |

## 近期新增功能

### AI模型Logo自动适配 (v2.1+)

系统内置15+主流AI供应商的Logo渲染支持，并在保存AI配置时自动获取未匹配品牌的Logo：

**内置品牌**：OpenAI、Anthropic (Claude)、Google (Gemini)、Azure OpenAI、DeepSeek、Moonshot (Kimi)、Zhipu (GLM)、百度 (文心一言)、阿里云 (通义千问)、腾讯云 (混元)、商汤 (SenseNova)、OpenRouter、Poolside、Nemotron (NVIDIA)、ox-alpha

**自动获取机制**：
- 保存AI配置时，前端调用 `autoFetchLogo()` 工具函数
- 首先通过 `detectBrandKey()` 检测是否为内置品牌（基于provider、api_base、model_name三级判断）
- 若为内置品牌，使用内置SVG渲染，无需远程请求
- 若为未知品牌（generic），从 `api_base` 提取主机名，拼接 DuckDuckGo Favicon 服务 URL：`https://icons.duckduckgo.com/ip3/{host}.ico`
- 远程Logo通过 `<img>` 标签加载，失败时自动回退到内置品牌渲染或首字母回退

**Logo渲染优先级**：远程图片 → 内置SVG Path → 首字母回退

### 系统任务响应字段映射增强 (v2.1+)

支持业务状态判断与失败原因提取：

- 新增 `is_status` 布尔字段：标识该映射是否用于业务成功/失败判断
- 新增 `success_value` 字符串字段：业务成功时的期望值（如 `"true"`, `"success"`, `"0"`）
- 新增 `error_field` 字符串字段：失败时提取错误信息的JSON路径（如 `msg`, `error.message`, `data.errMsg`）

**判定逻辑**：
1. 若 `is_status=true` 且响应中该字段值 == `success_value` → 业务成功
2. 若 `is_status=true` 且响应中该字段值 != `success_value` → 业务失败，提取 `error_field` 作为失败原因
3. 若 `is_status=false` → 仅作普通字段映射，不参与业务判断

### 开放API调用记录与统计优化 (v2.1+)

- 调用记录新增 `session_id` 列，支持按会话聚合展示
- 会话ID自动派生：基于 密钥ID + 首条user消息内容 SHA256 前32位，适配OpenAI协议无原生会话概念的场景
- 统计卡片随筛选条件实时刷新（密钥/模型/状态/时间/会话ID）
- 新增"会话聚合视图"：按session_id GROUP BY，显示对话数、Token总量、平均耗时、成功率、涉及模型列表
- 展开行懒加载会话明细，详情对话框支持Markdown渲染AI回复
- 调用方IP修复：支持IPv4映射IPv6（`::ffff:1.2.3.4`）、带端口IP、链路本地地址过滤、MAC地址识别回退

## 技术栈

**后端**：Flask + SQLAlchemy + PyJWT + Jinja2 + openpyxl + sshtunnel + croniter + MCP SDK + httpx

**前端**：Vue3 + Vite + Element Plus + Pinia + Vue Router + marked + highlight.js

**数据库**：SQLite（应用库）+ MySQL/PostgreSQL/SQLServer（业务库）

## 变更日志

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-08-25 | v2.1 | AI模型Logo自动适配（内置15+品牌+DuckDuckGo Favicon兜底）；系统任务响应字段映射支持业务状态判断；开放API调用记录新增session_id会话聚合；调用方IP修复（IPv4映射IPv6/带端口/链路本地过滤） |
| 2026-08-24 | v2.0 | 开放API调用记录与统计优化（会话聚合/统计随筛选/卡片化展示）；MCP服务器管理；代付提现增强；系统任务JSON输入框支持美化/压缩/转义 |
