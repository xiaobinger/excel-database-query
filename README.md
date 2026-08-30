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
- **多Agent协作**：工单指派给AI时可配置监督者Agent，执行者Agent负责执行工单任务，监督者Agent审查执行结果是否满足要求并打分（0-100），不满足则反馈返工，循环协作直到验收通过（协作轮数工单级可配置，默认3轮）；监督者可被授权「确认执行」——工单进入待确认状态时由监督者直接确认/拒绝，无需提交者人工介入
- **Headroom上下文压缩**：智能识别内容类型（JSON/日志/代码/文本），应用针对性压缩策略，节省60-95%输入token；支持按模型独立启用，实时展示压缩率和节省token统计

### 代付流程编排
- **流程模板管理**：步骤列表式配置，支持拖拽排序节点
- **节点配置**：每个节点独立配置支付动作（通道/接口/环境/实时代付/跑批步骤）
- **条件流转**：基于当前节点响应字段值判断（等于/不等于/包含/大于/小于/成功/失败/在列表等），支持引用任意节点结果（`nodeId.fieldName`）
- **循环执行**：节点可配置定时循环，支持多退出条件（AND/OR逻辑），满足条件后继续流转
- **失败即停**：节点失败时流程立即停止，不会继续执行下一节点（资金安全）
- **防重复执行**：多重安全检查确保同一行数据不会被重复处理（状态检查/时间检查/运行记录检查/调度防重入）
- **节点通知**：每个节点可配置失败通知、结束通知，支持邮件模板变量替换
- **通知模板管理**：统一管理通知模板（名称/标题/接收人/内容/状态），流程编排时下拉选择引用
- **执行记录**：每笔数据独立流程实例，实时查看执行状态与节点日志
- **流程走势图**：横向排列展示流程节点，直观查看执行进度与状态（成功/失败/等待/执行中）
- **后台调度**：守护线程每5秒检查待执行实例，驱动循环节点与流程推进
- **权限控制**：菜单权限 `pay_flow`（流程编排）/ `pay_flow_executions`（执行记录），支持角色权限独立配置

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
│   │   │   ├── pay_flow.py    # 代付流程编排（模板/实例/节点执行记录）
│   │   │   ├── system_task.py # 系统任务（含响应字段映射）
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
│   │   │   ├── pay_flow_routes.py # 代付流程编排API
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
│   │   │   ├── pay_flow_service.py    # 代付流程引擎（节点推进/条件流转/循环）
│   │   │   ├── pay_flow_scheduler.py  # 代付流程后台调度器
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
│   │   │   ├── PayFlowManager.vue          # 代付流程编排管理
│   │   │   ├── PayFlowExecutions.vue       # 代付流程执行记录
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
| 代付流程 | `/api/pay-flow/*` | 流程模板CRUD、发起流程、执行记录、走势动画 |

## 近期新增功能

### 工单多Agent协作：执行者 + 监督者 (v2.4.0)

**多Agent协作模式**：工单指派给AI时，可额外配置一个监督者Agent，由执行者Agent负责执行任务、监督者Agent审查执行结果，循环协作直到验收通过：

**协作机制**：
- **执行者Agent**：工单的 assignee_agent，负责调用系统工具（导出/查询/系统任务/信息查询/分润/代付等）实际处理工单
- **监督者Agent**：工单的 supervisor_agent_id，不调用工具，纯审查执行者的处理结果是否真正执行了任务、结果是否满足提交人要求
- **循环协作**：执行者执行一轮 → 监督者审查 → 验收通过则完结 / 不通过则反馈给执行者重新处理，直到验收通过或达到最大协作轮数
- **监督者评分**：监督者审查时对执行结果质量打分（0-100分），验收通过通常不低于60分；最终评分记录在工单 `final_score`，每轮评分记录在协作日志中，工单详情页按分数着色展示（≥80绿/≥60橙黄/<60红）
- **轮数可配置**：最大协作轮数工单级可配置（1-20轮，默认3），创建/重指派工单时可选，超过则强制完结并注明未完全验收
- **异步任务审查**：导出/查询/分润/代付等异步任务执行完成后，同样由监督者审查执行结果
- **监督者授权确认执行**：Agent管理页可为监督者开启「授权确认执行」，授权后工单进入「待确认」状态（SQL数据变更、生产环境代付提现）时，由监督者审查并直接确认/拒绝执行，无需提交者人工介入；拒绝则转待指派
- **协作日志**：每轮执行者与监督者的交互（角色/轮次/结论/评分/确认决策）实时记录，工单详情页以时间线形式展示

**Agent角色配置**：
- Agent管理页新增「角色」字段：通用（general）/ 执行者（executor）/ 监督者（supervisor）
- 监督者可配置「授权确认执行」开关（仅监督者角色显示）
- 创建工单、重新指派工单时，可在选择AI Agent的同时选择监督者Agent（监督者与执行者不能相同，监督者选项标注「可自动确认」）

**技术实现**：
- `backend/app/models/ai_agent.py`：AiAgent 新增 `agent_role` / `can_confirm_execution` 字段
- `backend/app/models/ticket.py`：Ticket 新增 `supervisor_agent_id` / `collaboration_rounds` / `collaboration_log` / `max_collaboration_rounds` / `final_score` 字段及 `supervisor_agent` 关系
- `backend/app/services/multi_agent_service.py`：新增多Agent协作编排服务（执行者工具循环 + 监督者审查评分 + 监督者确认执行决策 + 异步任务审查 + 工单级轮数控制）
- `backend/app/routes/ticket_routes.py`：`_process_ticket_with_ai_async` 检测到监督者时委托多Agent服务；异步回调接入监督者审查；create/update_draft/reassign 支持 `supervisor_agent_id`；`list_ai_agents` 返回 `agent_role`
- `backend/app/routes/agent_routes.py`：create/update 支持 `agent_role` / `can_confirm_execution`
- 前端：`AgentManager.vue` 角色配置与展示；`TicketManager.vue` 监督者选择、协作日志时间线展示

### 运营数据看板统计指标面板 (v2.3.22)

**单Y轴字段时动态展示统计指标**：
- 当图表 Y 轴仅选择 1 个数值字段时，图表区域右上角自动显示四项关键统计指标：最大值、最小值、平均值、中位数
- 指标面板支持大数智能格式化（万/亿），等宽数字字体（tabular-nums）对齐
- 面板带入场滑动动画，视觉上与图表区域融为一体
- 切换 Y 轴字段数量或更换字段时自动重算，无需手动操作

### 工单对话框关闭自动暂存草稿 (v2.3.21)

**防误关闭内容丢失**：
- 工单创建/编辑对话框关闭时（X按钮、取消按钮、ESC键），自动检测是否有内容（标题或正文），有则静默暂存为草稿
- 成功提交或手动暂存后关闭不重复保存（`justSubmitted` 标志位控制）
- 新工单调用 `create` API 创建草稿，已有草稿调用 `updateDraft` API 更新
- 附件 ID 一并关联保存，对话框关闭后清理本地状态

### 系统任务SQL脚本支持列表参数 (v2.3.20)

**IN 子句列表参数**：
- 系统任务 SQL 脚本类型支持 `IN (:param)` 语法，参数值为列表时自动展开为 `IN (:param_0, :param_1, ...)`
- 参数值来源支持：① 前端列表类型参数（tag 标签输入）② 逗号/中文逗号分隔的文本字符串（自动检测并拆分）
- 后端 `_execute_sql` 新增 `list_params` 分离逻辑，SQL 语句正则展开，绑定参数逐个生成
- 前端 params_config 新增「列表」类型，执行对话框渲染为标签输入组件（回车添加、逗号批量、标签可删除）
- 兼容已有 Script 的 `multi: true` 文本参数（逗号分隔输入同样触发 IN 展开）

### 看板表格图表视觉升级 (v2.3.19)

**表格类图表重新设计**：
- 表头：纯色蓝底 → 深石板色渐变（`#334155→#1e293b`）+ 字距 + 内阴影高光，粘性吸顶
- 行：极简斑马纹（奇数行微灰）+ 悬浮高亮 + 左侧主色指示条（inset box-shadow 实现）
- 入场动效：行交错淡入上滑（`--row-delay` 内联变量控制，18ms/行，封顶220ms）
- 百分比进度条：加粗至 6px 全圆角，翡翠绿渐变 + 外发光，`scaleX` 弹性展开动画（与行同步延迟）
- 容器：10px 圆角 + 双层柔和投影 + 自定义细滚动条（6px 圆角胶囊）

**图表类型切换按钮**：
- 英文文本按钮 → 圆角胶囊按钮（图标 + 中文标签：折线/柱状/面积/饼图/散点/表格/混合）
- 激活态主色渐变 + 投影，悬浮态浅色晕染

### 分组图标选择 + 撤销默认菜单配置改动 (v2.3.18)

**分组图标选择**：
- 系统地图「新建分组」「编辑分组」对话框新增图标选择器（64 个常用 Font Awesome 图标，网格展示 + 实时预览）
- 此前新建分组的图标写死为 `fa-folder`，无法为工单中心/代付管理/业务中心等自定义分组选择贴切图标
- 原「改名」按钮升级为「编辑」，可同时修改分组名称和图标

**撤销未经授权的默认菜单配置改动**：
- 回退 v2.3.16 中擅自向 `DEFAULT_MENU_CONFIG`（后端）添加的 4 个菜单项（代付提现/代付流程编排/代付流程执行记录/工单统计），恢复原有默认排版
- 说明：用户侧边栏菜单实际来源于数据库 `menu_config`（系统地图保存的自定义配置），代码中的默认配置仅在数据库无配置时生效

### 工单列表显示修复 (v2.3.17)

**Bug修复**：
- 修复 TicketManager.vue 中 `assigneeFilter`、`businessSystemFilter`、`dateFilter` 三个筛选变量未用 `ref()` 声明的问题
- 这些变量在模板中用 `v-model` 绑定，但 `<script setup>` 中缺少声明，导致 `fetchTickets` 访问 `.value` 时抛出 `TypeError`，被空 `catch` 捕获后设置空列表
- 同时补充了缺失的 `resetTicketFilters` 函数

### 菜单图标优化 + 列表筛选增强 (v2.3.16)

**菜单图标优化**：
- 工单管理：`fa-ticket` → `fa-tasks`（任务管理更通用）
- 工单统计：`fa-chart-bar` → `fa-chart-pie`（统计分析）
- 代付提现：`fa-money-bill-wave` → `fa-wallet`（钱包/资金）
- 代付流程编排：`fa-project-diagram` → `fa-route`（流程路由）
- 代付流程执行记录：`fa-stream` → `fa-list-check`（执行记录）
- 业务系统：`fa-th-large` → `fa-building`（业务/组织）

**列表筛选增强**：
- **工单管理**：新增指派人筛选、涉及系统筛选、时间范围筛选
- **执行历史**：新增任务类型筛选（查询/导出）、关键词搜索、时间范围筛选
- **代付流程编排**：新增模板名称搜索、启用/禁用状态筛选
- **代付流程执行记录**：新增时间范围筛选
- **业务系统**：新增SSO状态筛选、启用状态筛选

### 看板表格紧凑化 + 视觉微调 (v2.3.15)

**表格紧凑化**：
- 单元格 padding 从 `7px 10px` 缩减为 `6px 5px`（th）/ `4px 5px`（td），列间距大幅收窄
- 标签列 max-width 从 160px 缩减为 120px
- 百分比列 min-width 从 100px 缩减为 70px，pct-val margin-left 从 58px 缩减为 40px
- 表头去除 `white-space: nowrap` 允许换行（避免过宽表头撑开）

### 看板表格美化 + 多数据源图表切换 (v2.3.14)

**表格渲染美化**：
- 渐变色表头（主题色渐变，白色文字），取代原来的灰色表头
- 斑马纹行（奇偶行不同背景色）+ hover 行高亮
- 数值列右对齐、等宽字体（monospace）、千分位格式化
- 百分比列：内嵌迷你进度条（渐变绿色填充）+ 数值标签，取代纯文本
- 第一列标签列加粗，超长文本省略号截断
- 圆角边框容器，表头 sticky 吸顶

**多数据源图表切换**：
- 分源展示（`_source` 列存在）时，每个图表卡片顶部自动出现数据源 tab 切换栏
- 点击"全部"显示所有源合并数据，点击具体源名称仅显示该源数据
- 切换 tab 后立即重新渲染当前图表（echarts / 表格均支持）
- 每个图表卡片独立维护 `activeSource` 状态，不同卡片可同时查看不同源
- 全屏模式也继承当前选中的数据源过滤

### 运营数据看板脚本统一 + 自定义时间范围 (v2.3.13)

看板脚本增删改统一到脚本管理页维护，看板页只保留脚本下拉选择；新增"自定义范围"时间维度。

**看板脚本统一**：
- `DataDashboard.vue`：移除脚本管理对话框及全部 CRUD 函数（newScript/editScript/saveScript/deleteScript），看板页仅保留脚本下拉选择 + 执行查询
- `dashboard_routes.py`：移除看板脚本 POST/PUT/DELETE 路由，仅保留 GET 只读列表
- `dashboard_service.py`：移除 `seed_default_scripts()` 函数
- `api/index.js`：移除 `createScript/updateScript/deleteScript` 三个 API 调用
- `DashboardScript` 模型类正式删除，`__init__.py` 迁移函数改用 raw SQL 读取旧表
- 脚本增删改全部通过脚本管理页（ScriptManager，`type='dashboard'`）维护

**自定义时间范围**：
- 前端新增 `custom` 维度 radio-button + `el-date-picker` daterange 选择器
- 后端 `build_dimension_params()` 新增 `custom` 维度：按跨度自动选择分组粒度（2年以上→按年，2月以上→按月，否则→按天）
- 后端 `execute_dashboard_query()` 接收 `start_date`/`end_date` 参数并纳入缓存 key
- 快捷查询保存/恢复自定义时间范围（`dp_start_date`/`dp_end_date` 字段，`DashboardQuickQuery` 模型新增）

### 运营数据看板崩溃根治：渲染异常 + 全站污染 + keep-alive 资源泄漏 (v2.3.12)

彻底修复运营数据看板打开报错、且崩溃后拖垮其他页面（需刷新整站）的三层叠加问题：

**根因分析**：
1. **首次渲染必崩**：`chartConfigs` 初始为空数组，而 `ensureChartConfigs()` 要等 `onMounted` 的异步加载完成后才执行——模板渲染 `chartConfigs[i - 1].xCol` 时取到 `undefined`，直接抛 `TypeError`，组件挂载即崩溃
2. **崩溃扩散全站**：`Layout.vue` 用 `<keep-alive>` 缓存所有页面，且 `main.js` 无全局错误处理——渲染异常未捕获沿组件树冒泡，破坏 Vue 内部状态后任何路由切换都渲染失败，表现为全站白屏需刷新
3. **keep-alive 资源泄漏**：`onBeforeUnmount` 在 keep-alive 缓存下永不触发，`resize` 事件监听器与 echarts 实例永不清理

**前端修复**（`frontend/src/views/DataDashboard.vue`）：
- `chartConfigs` 初始值直接填充 1 个默认配置，且 `ensureChartConfigs()` 提前到 `onMounted` 同步段执行
- 新增 `chartAt(idx)` 安全访问函数：模板所有 `chartConfigs[i].xxx` 访问改为 `chartAt(i).xxx`，索引越界自动补全默认配置，从机制上杜绝 `undefined` 属性访问
- 新增 `onDeactivated`/`onActivated` 适配 keep-alive：切走时移除 `resize` 监听并 `dispose` 全部图表实例；切回时恢复监听并重新渲染（`lastResult` 有值时）
- 统一 `disposeAllCharts()` 清理函数（失活/卸载共用）；`setChartRef` 在元素卸载（`el` 为 null）时删除引用
- `renderChart`/`handleDrill`/`exportExcel`/`openFullscreen` 增加配置缺失防御；`layoutCount` 缩小时 dispose 超出范围的图表实例

**全局兜底**（`frontend/src/main.js`）：
- 新增 `app.config.errorHandler`：单页组件渲染出错时仅记录控制台日志并拦截冒泡，不再破坏整站组件树——单页崩溃只影响单页，刷新该页即可恢复

### 运营数据看板脚本统一到 scripts 表 (v2.3.11)

废弃旧的 `dashboard_scripts` 表，看板脚本 CRUD 全面切换到统一的 `scripts` 表（`type='dashboard'`），与脚本管理页同源：

**后端改造**：
- `backend/app/routes/dashboard_routes.py`：看板脚本 CRUD（`/api/dashboard/scripts`）从 `DashboardScript` 模型切换到 `Script` 模型（`type='dashboard'`），新增 `_script_to_dashboard_dict` 辅助函数保持前端 `sql` 字段名兼容；删除改为软删除（`is_active=False`）
- `backend/app/services/dashboard_service.py`：`seed_default_scripts()` 改用 `Script` 模型写入示例脚本
- `backend/app/__init__.py`：启用 `_migrate_dashboard_scripts_to_scripts()` 迁移函数（启动时自动检查旧 `dashboard_scripts` 表并同步到 `scripts` 表），`_seed_dashboard_scripts()` 简化为只检查 `scripts` 表

**前端修复**：
- `frontend/src/views/DataDashboard.vue`：`loadScripts`/`loadConnections`/`loadQuickQueries` 增加 try/catch 错误处理，API 失败时降级为空数组而非页面崩溃；`deleteScript` 增加确认对话框取消异常处理

**数据迁移**：
- 启动时自动检测旧 `dashboard_scripts` 表是否存在，存在则同步未迁移的脚本到 `scripts` 表（按名称去重）
- 旧 `DashboardScript` 模型类保留用于迁移，迁移完成后可安全废弃

### 工单草稿暂存 (v2.3.8)

工单编辑时支持暂存为草稿，未提交的草稿工单下次可从列表进入重新编辑并提交：

**功能说明**：
- **暂存草稿**：创建工单时点击"暂存草稿"按钮，仅标题必填，内容与指派人可为空
- **草稿列表**：草稿工单在工单列表中显示"草稿"标签（仅创建人可见），点击标签可直接进入编辑
- **编辑草稿**：从列表或详情对话框点击"编辑草稿"，预填草稿数据后修改，可再次暂存或提交
- **提交草稿**：草稿编辑完成后点击"提交工单"，校验必填字段（内容/指派人）后转为正式工单
- **AI草稿**：草稿指派给AI时，提交后自动触发AI处理

**技术实现**：
- `backend/app/models/ticket.py`：Ticket模型新增`is_draft`布尔字段（区分草稿与正式工单），状态流转新增`draft`状态
- `backend/app/routes/ticket_routes.py`：
  - `create_ticket()` 支持`is_draft`参数：草稿模式跳过内容与指派人校验
  - 新增`PUT /<id>/draft`：更新草稿（仅创建人可操作）
  - 新增`POST /<id>/submit`：提交草稿（校验必填字段后转为submitted状态）
  - `list_tickets()` 列表查询扩展：普通用户可见自己创建的草稿
- `frontend/src/api/index.js`：新增`updateDraft`/`submitDraft` API方法
- `frontend/src/views/TicketManager.vue`：
  - 创建对话框新增"暂存草稿"按钮
  - 列表状态列新增"草稿"标签（可点击直接编辑）
  - 详情对话框新增"编辑草稿"和"提交工单"按钮（仅创建人可见）
  - `statusLabels`/`statusTagType` 新增`draft`状态
  - `openCreateDialog` 支持预填草稿数据（`editingDraftId`标记）

### 工单AI处理Token消耗统计 (v2.3.6+)

工单指派给AI处理时，统计并展示该工单在整个AI处理过程中消耗的token相关指标，包括Headroom压缩指标和参与的AI模型：

**统计指标**：
- **总消耗Token**：AI处理该工单所有调用（工具循环、归总回复、最终回复）的token合计
- **Prompt Tokens**：输入token消耗合计
- **Completion Tokens**：输出token消耗合计
- **缓存创建/读取**：Cache Creation / Cache Read token消耗
- **Headroom原始Token**：压缩前原始token合计
- **Headroom节省Token**：压缩节省token合计 + 压缩比例
- **参与AI模型**：去重记录所有参与处理的AI模型列表

**展示位置**：
1. **工单详情对话框**（TicketManager.vue）：在"AI处理结果"下方展示"AI Token 消耗指标"区块，含总消耗标签、参与模型标签、6项细分指标
2. **工单统计页**（TicketAnalytics.vue）：AI Agent处理统计表格新增"Token消耗"和"Headroom节省"两列；汇总行新增"Token总消耗"和"Headroom节省+压缩比例"标签

**技术实现**：
- `backend/app/models/ticket.py`：Ticket模型新增9个字段（`ai_total_tokens`/`ai_prompt_tokens`/`ai_completion_tokens`/`ai_cache_creation_tokens`/`ai_cache_read_tokens`/`ai_headroom_original_tokens`/`ai_headroom_saved_tokens`/`ai_headroom_compression_ratio`/`ai_models_used`）+ `accumulate_ai_token_usage()` 累加方法
- `backend/app/routes/ticket_routes.py`：`_process_ticket_with_ai_async()` 中3处 `chat_with_failover()` 调用后捕获并累加token指标；`/analytics` 接口新增按Agent聚合的token统计查询和汇总
- 前端：`TicketManager.vue` + `TicketAnalytics.vue` 展示组件

### Headroom上下文压缩 (v2.3+)

基于内容感知的智能上下文压缩层，自动识别消息内容类型并应用最优压缩策略，大幅降低AI对话的输入token消耗：

**核心能力**：
- **内容类型识别**：自动识别JSON数组、日志、代码、文本四种内容类型
- **SmartCrusher（JSON压缩）**：基于字段方差统计，高方差字段完整保留，低方差字段提取值列表，节省70-90% token
- **LogCompressor（日志压缩）**：保留ERROR/FATAL/WARN级别日志行，压缩DEBUG/INFO冗余行，节省85-95% token
- **CodeCompressor（代码压缩）**：保留函数签名、类定义、导入语句等结构信息，压缩函数体实现，节省40-70% token
- **TextCrusher（文本压缩）**：去除重复段落、冗余格式、无意义填充词；单段落长文本按句子截断保留首尾；多段落长文本保留首尾段落省略中间；重复行合并，节省30-99% token
- **按模型独立配置**：每个AI模型可单独启用/禁用Headroom压缩
- **实时统计展示**：对话消息、缓存统计页面实时展示压缩率和节省token数
- **对外API支持**：外部API调用（OpenAI兼容端点、自定义端点）同样支持Headroom压缩，响应中返回压缩统计（`headroom`字段），调用日志记录压缩指标和节省token

**压缩策略对比**：

| 内容类型 | 压缩策略 | 节省率 | 保留内容 |
|---------|---------|--------|---------|
| JSON数组 | SmartCrusher | 70-90% | 高方差字段完整、低方差字段值列表 |
| 日志 | LogCompressor | 85-95% | ERROR/FATAL/WARN行、关键上下文 |
| 代码 | CodeCompressor | 40-70% | 函数签名、类定义、导入语句 |
| 文本 | TextCrusher | 30-60% | 关键信息、去重段落 |

**使用方式**：
1. 在「系统配置 → AI模型配置」中编辑目标模型
2. 开启「Headroom压缩」开关
3. 保存后，该模型的AI对话将自动应用压缩，模型标签栏显示绿色压缩图标
4. 在「缓存管理」页面查看压缩统计卡片（压缩前Tokens、节省Tokens、压缩率、实际消耗Tokens）
5. 在AI对话页面消息下方查看单条消息的压缩统计

**压缩阈值**：
- 内容长度阈值：50字符（低于此值不压缩）
- JSON数组阈值：3项以上触发压缩
- 日志行数阈值：5行以上触发压缩
- 代码行数阈值：10行以上触发压缩
- 文本压缩阈值：500字符以上触发压缩

**技术实现**：
- `backend/app/services/headroom_service.py`：HeadroomCompressor核心实现（含单段落长文本句子截断策略）
- `backend/app/services/ai_service.py`：集成压缩入口 `compress_if_enabled()`（非流式路径）
- `backend/app/routes/ai_routes.py`：流式对话路径 `send_message_stream` → `generate()` 中调用 `compress_if_enabled()`，done事件和消息保存传递 `headroom_stats`；流式请求添加 `stream_options: {include_usage: True}` 确保token统计正确
- `backend/app/models/ai_config.py`：`enable_headroom`配置字段
- `backend/app/models/ai_chat.py`：`headroom_original_tokens`/`headroom_saved_tokens`/`headroom_compression_ratio`统计字段
- `backend/app/services/open_api_service.py`：对外API调用时应用Headroom压缩（`_chat_single`/`chat_once`/`stream_chat`）
- `backend/app/routes/open_api_routes.py`：对外API响应中包含`headroom`统计字段
- `backend/app/models/api_call_log.py`：调用日志记录`headroom_original_tokens`/`headroom_saved_tokens`/`headroom_compression_ratio`
- 前端配置页：`SystemConfig.vue`
- 前端统计展示：`CacheManager.vue`、`AiChat.vue`

### 代付流程编排系统 (v2.2+)

支持用户自定义代付流程的走势与流转条件，实现灵活的多步骤自动化处理：

**核心能力**：
- **步骤列表式配置**：卡片式节点管理，支持添加/删除/排序
- **节点支付配置**：每个节点独立配置支付动作（通道/接口/环境/实时代付/跑批步骤）
- **条件流转引擎**：基于当前节点响应字段值判断（eq/neq/contains/gt/lt/success/fail/in/not_in等运算符），支持引用任意节点结果（`nodeId.fieldName`）
- **定时循环执行**：节点可配置循环间隔、最大次数、多退出条件（AND/OR逻辑），满足条件后继续流转
- **失败即停机制**：节点失败时流程立即停止，不会继续执行下一节点（资金安全）
- **防重复执行**：多重安全检查确保同一行数据不会被重复处理（状态检查/时间检查/运行记录检查/调度防重入）
- **节点通知配置**：每个节点可配置失败通知、结束节点标记及结束通知，支持邮件模板变量替换
- **汇总通知**：发起流程时可选启用汇总通知，批次结束后一次性发送汇总邮件（总笔数、成功/失败笔数、成功/失败金额、明细列表），节点级单独通知自动失效
- **每笔数据独立实例**：每行Excel数据创建独立流程实例，互不影响
- **可视化走势动画**：实时展示流程进度，脉冲动画标识当前运行节点
- **执行日志详情**：每个节点记录完整执行日志，支持查看失败原因
- **后台调度驱动**：守护线程每5秒检查待执行实例，自动推进流程
- **批次聚合视图**：执行记录按批次聚合展示，支持展开查看单条记录、单条重试、批次重试（仅当所有流程都在第一个节点失败时才允许）

**数据模型**：
- `PayFlowTemplate`：流程模板（节点定义、流转条件）
- `PayFlowExecution`：流程实例（每笔数据一个，含循环状态、汇总通知字段）
- `PayFlowNodeExecution`：节点执行记录（日志、结果、时间戳）

**API端点**：
- `GET/POST/PUT/DELETE /api/pay-flow/templates`：模板CRUD
- `POST /api/pay-flow/start`：发起流程（支持 `summary_notify_enabled` / `summary_notify_template_id` 参数）
- `GET /api/pay-flow/executions`：执行记录列表
- `GET /api/pay-flow/executions/{id}`：执行详情（含节点日志）
- `POST /api/pay-flow/executions/{id}/cancel|retry`：取消/重试
- `GET /api/pay-flow/batches`：批次列表（按batch_id聚合，含分页/关键字搜索/统计）
- `GET /api/pay-flow/batches/{batch_id}/detail`：批次详情（含所有执行记录）
- `GET /api/pay-flow/batches/{batch_id}/summary`：批次摘要
- `POST /api/pay-flow/batches/{batch_id}/retry`：批次重试（仅当所有失败实例在首节点失败时允许）

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

### 系统任务参数来源脚本 (v2.1+)

API类型和本地脚本类型的系统任务支持**从SQL脚本动态获取参数**：

**功能说明**：
- 新建/编辑任务时可开启"从脚本获取参数"选项
- 选择一个SQL脚本作为参数来源，指定执行数据库
- 支持配置字段映射：将脚本返回的字段映射到任务参数名
- 执行任务时，系统先运行参数来源脚本获取查询结果（取第一行），再将结果合并到任务参数中
- **若参数来源脚本执行失败或返回为空，将中止主任务执行并记录错误日志**

**典型场景**：
- API接口需要动态Token：先执行SQL查询获取最新Token，再传给API
- 脚本需要动态配置：从数据库读取配置参数，再执行本地脚本
- 多步骤任务：先查询数据库获取业务数据，再调用外部接口处理

**字段映射规则**：
- 配置映射：`source_field`（脚本返回字段）→ `target_param`（任务参数名）
- 不配置映射：自动合并所有字段（参数名与脚本字段名相同时自动匹配）

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
| 2026-08-30 | v2.4.0 | 工单多Agent协作（执行者+监督者）：工单指派给AI时可额外配置监督者Agent，执行者Agent执行工单任务、监督者Agent审查执行结果是否满足要求并打分（0-100），不满足则反馈返工循环协作直到验收通过；最大协作轮数工单级可配置（1-20轮，默认3）；异步任务（导出/查询/分润/代付）完成后同样由监督者审查；**监督者授权确认执行**（Agent管理页为监督者开启后，工单进入「待确认」状态如SQL数据变更/生产代付时，由监督者直接审查确认/拒绝执行，无需提交者人工介入）；Agent管理新增角色字段与授权开关；工单创建/重指派支持选择监督者与轮数配置；工单详情展示监督评分与协作日志时间线；后端新增`multi_agent_service.py`、Ticket模型新增`supervisor_agent_id`/`collaboration_rounds`/`collaboration_log`/`max_collaboration_rounds`/`final_score`、AiAgent新增`agent_role`/`can_confirm_execution` |
| 2026-08-29 | v2.3.22 | 运营数据看板统计指标面板：图表Y轴仅选择1个数值字段时，图表区域右上角自动显示四项关键统计指标（最大值、最小值、平均值、中位数）；大数智能格式化（万/亿），等宽数字字体对齐；面板带入场滑动动画；切换Y轴字段时自动重算 |
| 2026-08-28 | v2.3.12 | 运营数据看板崩溃根治：三层叠加问题修复——①`chartConfigs`初始空数组导致首次渲染`undefined.xCol`崩溃（初始填充+`chartAt()`安全访问+`ensureChartConfigs`提前到同步段）；②渲染异常沿组件树冒泡破坏全站（keep-alive缓存下任何路由切换都白屏，`main.js`新增全局`errorHandler`兜底拦截）；③keep-alive下`onBeforeUnmount`永不触发的资源泄漏（新增`onDeactivated`/`onActivated`适配：切走清理`resize`监听与echarts实例、切回恢复监听并重渲染）；`setChartRef`卸载时清引用、`layoutCount`缩小时dispose多余图表实例、多处函数增加配置缺失防御 |
| 2026-08-28 | v2.3.11 | 运营数据看板脚本统一到scripts表：废弃旧`dashboard_scripts`表，看板脚本CRUD全面切换到`scripts`表（`type='dashboard'`）；后端`dashboard_routes.py`改用`Script`模型查询/创建/更新/删除看板脚本，新增`_script_to_dashboard_dict`辅助函数保持前端字段兼容；`dashboard_service.py`种子函数改用`Script`模型；`__init__.py`启用迁移函数（自动检测并同步旧`dashboard_scripts`表数据）；前端`DataDashboard.vue`增加API调用错误处理（try/catch降级为空数组避免页面崩溃）；删除改为软删除（`is_active=False`） |
| 2026-08-28 | v2.3.10 | 修复工单AI处理多系统任务只执行最后一个的bug：AI工具调用循环中多个SQL系统任务待确认时，`pending_system_task`单变量被覆盖只保留最后一个；改为`pending_system_tasks`列表收集所有任务，`pending_action`存储为`{'tasks': [...]}`格式；重写`_execute_pending_action_async`支持多任务顺序执行（遇失败中止），兼容旧格式单任务字典；前端待确认banner显示任务列表，确认对话框列出所有待执行任务；修复`cancel_ticket_action`对新格式的兼容性 |
| 2026-08-28 | v2.3.9 | 运营数据看板脚本集成到脚本管理：看板脚本类型（`dashboard`）统一纳入现有脚本管理系统，与查询/导出/系统/字典脚本同页管理；Script模型新增`chart_type`/`conn_name`/`merge_conn_names`字段，支持图表类型、主数据源、多源合并查询配置；前端ScriptManager新增"看板脚本"类型选项，选择后显示图表类型选择、数据源选择、合并数据源多选等专属表单字段；新增从旧`dashboard_scripts`表的迁移逻辑，自动同步历史看板脚本数据 |
| 2026-08-28 | v2.3.8 | 工单草稿暂存：创建工单支持暂存为草稿（仅标题必填，内容/指派人可选）；草稿在列表中显示"草稿"标签，点击可直接进入编辑；详情对话框新增"编辑草稿"/"提交工单"按钮；新增`PUT /<id>/draft`更新草稿接口、`POST /<id>/submit`提交草稿接口；`create_ticket`支持`is_draft`参数；列表查询扩展普通用户可见自己的草稿 |
| 2026-08-28 | v2.3.7 | 工单AI处理Token消耗统计：工单指派给AI时，统计并展示AI处理过程消耗的token指标（总Token/Prompt/Completion/缓存创建/缓存读取），Headroom压缩指标（原始/节省/压缩率），参与的AI模型列表；工单详情对话框新增"AI Token 消耗指标"区块；工单统计页AI Agent表格新增Token消耗和Headroom节省列，汇总行新增Token总消耗标签 |
| 2026-08-27 | v2.3.5 | 修复流式对话路径Headroom压缩缺失：流式对话（`send_message_stream`）完全未调用`compress_if_enabled`，导致headroom在流式对话中不生效；修复后在`_attempt`循环中添加压缩调用，并在done事件和消息保存中传递`headroom_stats`（original_tokens/saved_tokens/compression_ratio）；修复token统计不工作：流式请求缺少`stream_options: {include_usage: True}`导致OpenAI流式API不返回usage数据，在两处流式请求中添加`stream_options`；删除工具循环中重复的usage提取代码（避免token统计翻倍）；增强纯文本压缩策略：新增单段落长文本按句子截断策略 |
| 2026-08-27 | v2.3.4 | Headroom压缩指标始终展示：对话消息下方和缓存统计页面即使未压缩也显示压缩指标（0 tokens/0%）；输入栏区分"将压缩"/"太短不压缩"/"未启用压缩"三种状态 |
| 2026-08-27 | v2.3.6 | AI会话管理对话详情展示完整指标：在会话管理页面"查看对话详情"对话框中，每条 assistant 消息下方展示耗时、token（输入/输出）、缓存（写入/命中）、Headroom 压缩指标（原文/压缩后/节省/压缩率），与实时对话页保持一致 |
| 2026-08-27 | v2.3.3 | AI对话输入框实时统计：输入区域下方展示已输入字符数、预计消耗token数、是否触发headroom压缩（绿色"将压缩"/灰色"不压缩"） |
| 2026-08-27 | v2.3.2 | 对外API支持Headroom压缩：外部API调用（OpenAI兼容端点、自定义端点）同样应用Headroom上下文压缩逻辑，响应中返回`headroom`统计字段（original_tokens/saved_tokens/compression_ratio），调用日志记录压缩指标和节省token |
| 2026-08-27 | v2.3.1 | Headroom上下文压缩优化：降低压缩阈值（内容50字符/JSON 3项/日志5行/代码10行/文本500字符）使更多消息被压缩；新增模型标签栏绿色压缩图标指示器（`headroom-badge`）；新增消息发送区域Headroom启用状态实时展示 |
| 2026-08-27 | v2.3.0 | 修复批次重试后不再次触发汇总通知：`retry_batch`/`retry_execution` 重置实例时未重置`summary_notify_sent`标记，首次通知后标记为True，重试执行完成后被`_try_trigger_summary_notification`跳过；两处重试逻辑均补充重置标记 |
| 2026-08-27 | v2.2.9 | 修复汇总通知邮件HTML标签不渲染问题：汇总通知邮件误用plain纯文本格式发送（节点通知均为html格式），模板中的HTML标签直接显示为原始文本；改为html格式发送，明细列表换行符由\n改为\<br\> |
| 2026-08-27 | v2.2.8 | 修复批次明细展开不显示问题：点击行首展开箭头未触发明细加载（executions始终为null）；"展开"按钮未调用表格toggleRowExpansion导致行不展开；轮询刷新后展开状态丢失。改为受控展开（expand-row-keys + expand-change事件统一处理数据加载与状态同步） |
| 2026-08-27 | v2.2.7 | 修复批次列表API 500错误：`func.case()`为非法SQLAlchemy用法导致生成非法SQL，改为标准`sqlalchemy.case()`；SUM结果由Decimal转为int避免JSON序列化问题 |
| 2026-08-27 | v2.2.6 | 代付流程执行记录改为批次聚合视图：按batch_id聚合展示批次统计（总数/成功/失败/运行中/待执行/已取消/进度），支持展开查看单条记录、单条重试、批次重试（仅当批次内所有流程都在第一个节点失败时才允许）；新增批次列表/详情/重试API |
| 2026-08-27 | v2.2.5 | 彻底修复节点重复执行问题：以数据库原子抢占（CAS，`UPDATE ... WHERE status IN ('pending','waiting')`）替代时间锁防重入，多个后端进程/线程并发分发同一实例时仅一个能抢占成功，其余直接跳过；调度器逻辑相应简化 |
| 2026-08-26 | v2.2.4 | 流程走势图改为横向排列；修复第一个节点重复执行问题（增加调度层防重入时间锁）；新增通知模板统一管理功能：在代付配置页集中创建/编辑/删除通知模板，流程编排时下拉选择引用 |
| 2026-08-26 | v2.2.3 | 代付流程执行记录新增单条删除与批量删除：表格行内删除按钮+多选批量删除；后端自动跳过运行中的记录；删除时联动清理节点执行日志 |
| 2026-08-26 | v2.2.2 | 代付流程编排修复：修复节点重复执行问题（双重防重复检查+递归调用优化）；修复失败后仍继续执行问题（节点失败立即停止+递归调用状态修复）；修复失败通知未生效问题（通知函数独立+增强日志） |
| 2026-08-26 | v2.2.1 | 代付流程编排增强：移除通知节点类型，改为每个节点可配置失败通知/结束通知；节点失败时流程立即停止；增加多重防重复执行检查（资金安全）；流转条件支持引用当前节点及任意节点结果（`nodeId.fieldName`）；循环退出条件支持多条件AND/OR逻辑 |
| 2026-08-26 | v2.2 | 代付流程编排系统：步骤列表式配置、双节点类型（支付/通知）、条件流转引擎、定时循环执行、每笔数据独立实例、可视化走势动画、后台调度驱动 |
| 2026-08-25 | v2.1 | AI模型Logo自动适配（内置15+品牌+DuckDuckGo Favicon兜底）；系统任务响应字段映射支持业务状态判断；开放API调用记录新增session_id会话聚合；调用方IP修复（IPv4映射IPv6/带端口/链路本地过滤） |
| 2026-08-24 | v2.0 | 开放API调用记录与统计优化（会话聚合/统计随筛选/卡片化展示）；MCP服务器管理；代付提现增强；系统任务JSON输入框支持美化/压缩/转义 |
