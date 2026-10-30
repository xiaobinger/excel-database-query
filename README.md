<div align="center">

<!-- 项目 Logo / ASCII Art -->
<pre>
 ███████╗ ██████╗ ██████╗ ███████╗ █████╗ ████████╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗╚══██╔══╝
 █████╗  ██║   ██║██████╔╝█████╗  ███████║   ██║   
 ██╔══╝  ██║   ██║██╔═══╝ ██╔══╝  ██╔══██║   ██║   
 ██║     ╚██████╔╝██║     ███████╗██║  ██║   ██║   
 ╚═╝      ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   
   ██████╗ ██╗   ██╗███████╗███████╗████████╗
  ██╔═══██╗██║   ██║██╔════╝██╔════╝╚══██╔══╝
  ██║   ██║██║   ██║█████╗  ███████╗   ██║   
  ██║▄▄ ██║██║   ██║██╔══╝  ╚════██║   ██║   
  ╚██████╔╝╚██████╔╝███████╗███████║   ██║   
   ╚══▀▀═╝  ╚═════╝ ╚══════╝╚══════╝   ╚═╝   
</pre>

<h1>Excel Database Query</h1>

<p><strong>企业级 Excel 数据库查询与导出平台</strong></p>
<p><em>Flask + Vue3 · 多数据库连接 · SSH隧道 · 智能匹配 · SQL模板 · 自动导出 · AI多Agent协作 · 代付流程编排</em></p>

<!-- 徽章 -->
<p>
  <img src="https://img.shields.io/badge/version-2.6.35-blue?style=flat-square" alt="version" />
  <img src="https://img.shields.io/badge/python-3.10+-yellow?style=flat-square&logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/vue-3-green?style=flat-square&logo=vuedotjs&logoColor=white" alt="vue" />
  <img src="https://img.shields.io/badge/flask-black?style=flat-square&logo=flask&logoColor=white" alt="flask" />
  <img src="https://img.shields.io/badge/mysql-8.0-orange?style=flat-square&logo=mysql&logoColor=white" alt="mysql" />
  <img src="https://img.shields.io/badge/license-internal-red?style=flat-square" alt="license" />
</p>

<p>
  <a href="#-核心功能">核心功能</a> · 
  <a href="#-ai-功能">AI 功能</a> · 
  <a href="#-代付流程编排">代付流程</a> · 
  <a href="#-快速开始">快速开始</a> · 
  <a href="#-api-概览">API</a> · 
  <a href="#-技术栈">技术栈</a> · 
  <a href="#-变更日志">变更日志</a>
</p>

</div>

---

## ✨ 项目亮点

<table>
<tr>
<td width="50%">

### 🚀 核心能力
- **批量查询** — 上传 Excel，自动匹配 SQL 脚本，批量查询多库
- **数据导出** — 一键从数据库导出到 Excel
- **自动导出** — Cron 定时触发，支持邮件通知
- **SQL 模板** — Jinja2 语法，支持按月分表 UNION ALL

</td>
<td width="50%">

### 🛡️ 企业特性
- **多数据库** — MySQL / PostgreSQL / SQL Server
- **SSH 隧道** — 安全连接内网数据库
- **RBAC 权限** — 菜单 + 按钮级精细控制
- **智能匹配** — 文件名自动推荐查询选项

</td>
</tr>
<tr>
<td>

### 🤖 AI 智能
- 多 Agent 协作（执行者 + 监督者）
- Headroom 上下文压缩（节省 60-95% Token）
- AI 技能自动学习与保存
- 15+ 供应商 Logo 自动适配

</td>
<td>

### 💰 代付流程
- 可视化流程编排（拖拽节点）
- 条件流转 + 循环执行
- 失败即停（资金安全）
- 防重复执行 + 批次聚合

</td>
</tr>
</table>

---

## 🎯 核心功能

<details>
<summary><strong>📊 查询执行</strong> — 上传 Excel 文件，自动执行数据库查询</summary>

- 上传 Excel 文件，选择查询选项，自动匹配 SQL 脚本
- 支持 `IN :value` 批量查询，自动分批执行
- 结果自动写回 Excel，支持多 Sheet
- 智能匹配：根据文件名自动推荐查询选项

</details>

<details>
<summary><strong>📤 导出任务</strong> — 直接从数据库导出数据到 Excel</summary>

- 基于导出选项配置参数，一键导出
- 支持多数据库联合查询合并结果
- 结果合并策略：合并 / 分离
- 支持列映射、主键更新

</details>

<details>
<summary><strong>⏰ 自动导出</strong> — Cron 定时触发导出任务</summary>

- Cron 表达式配置执行计划
- 支持邮件通知（附件 / 正文）
- 手动重发邮件功能
- 任务状态实时监控

</details>

<details>
<summary><strong>📝 SQL 模板</strong> — Jinja2 语法动态生成 SQL</summary>

- 按月分表场景：`SELECT * FROM transaction_{{ m }}`
- 支持日期范围、文本、数字变量类型
- 自动渲染并执行

</details>

---

## 🤖 AI 功能

<table>
<tr>
<td width="25%">

**🧠 多 Agent 协作**

执行者负责执行工单任务，监督者审查结果并打分（0-100），循环协作直到验收通过。

- 最大协作轮数可配置（1-20 轮）
- 监督者可授权「确认执行」
- 协作日志时间线展示

</td>
<td width="25%">

**🔀 大小模型协作路由**

路由策略支持开启"大小模型协作"：大模型负责推理分析（查询、多步推理），小模型负责整理最终输出；简单问答（问候、闲聊）由小模型一步完成，无需调用大模型。支持自定义大/小模型列表，留空自动按模型名（mini/flash/lite等）分类。

</td>
<td width="25%">

**🗜️ Headroom 上下文压缩**

智能识别内容类型，应用针对性压缩策略：

| 内容类型 | 策略 | 节省率 |
|---------|------|--------|
| JSON 数组 | SmartCrusher | 70-90% |
| 日志 | LogCompressor | 85-95% |
| 代码 | CodeCompressor | 40-70% |
| 文本 | TextCrusher | 30-60% |

</td>
<td width="25%">

**🎨 AI 模型 Logo 自动适配**

内置 15+ 主流供应商 Logo：

OpenAI · Anthropic · Google · Azure · DeepSeek · Moonshot · Zhipu · 百度 · 阿里 · 腾讯 · 商汤 · OpenRouter · Poolside · Nemotron · ox-alpha

未知品牌自动通过 DuckDuckGo Favicon 获取。

</td>
</tr>
</table>

### 💬 AI 对话特性

| 特性 | 说明 |
|------|------|
| **大小模型协作** | 大模型负责推理分析（查询/多步推理），小模型负责整理输出；简单问答小模型一步完成 |
| **插话/排队** | 🛑 立即停止并采纳 · ⚡ 插话发送 · 🕐 排队发送 |
| **技能保存** | AI 自动保存用户要求的 SKILLS/规则 |
| **用户感知** | AI 感知用户角色，区别尊称 |
| **排队编辑** | 排队中消息支持行内编辑 |

---

## 💰 代付流程编排

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  节点A   │───▶│  节点B   │───▶│  节点C   │───▶│  完成   │
│  代付    │    │  验证    │    │  通知    │    │  ✅    │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
                    │
                    ▼ 失败
               ┌─────────┐
               │  停止   │
               │  ❌    │
               └─────────┘
```

- **流程模板管理** — 卡片式节点配置，支持拖拽排序
- **条件流转** — 基于节点响应字段值判断（eq/neq/contains/gt/lt/success/fail）
- **循环执行** — 支持多退出条件（AND/OR 逻辑）
- **失败即停** — 资金安全保障，节点失败立即停止
- **防重复执行** — 多重安全检查（状态/时间/运行记录/调度防重入）
- **通知模板** — 统一管理，流程编排时下拉选择
- **可视化走势** — 横向排列展示流程节点，实时查看执行进度

---

## 📁 项目结构

```
excel-database-query/
├── backend/                    # Flask 后端
│   ├── app/
│   │   ├── models/            # 数据模型（33 张表）
│   │   ├── routes/            # API 路由（30+ 模块）
│   │   ├── services/          # 业务服务
│   │   └── utils/             # 工具类
│   ├── config.yaml            # 应用配置
│   └── requirements.txt       # Python 依赖
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── views/             # 页面（30+ 页面）
│   │   ├── components/        # 公共组件
│   │   ├── stores/            # Pinia 状态管理
│   │   └── utils/             # 工具函数
│   └── package.json
├── database/
│   └── init.sql               # 数据库初始化脚本
└── docs/                       # 项目文档
```

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境 |
| MySQL | 8.0+ | 元数据存储 |

### 1️⃣ 后端启动

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

### 2️⃣ 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 3️⃣ 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 超级管理员 |

---

## ⚙️ 配置说明

```yaml
# config.yaml
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

security:
  secret_key: "your-secret-key"
  jwt_secret_key: "your-jwt-secret-key"
  encryption_key: "your-encryption-key-32-bytes-long!"

smart_match:
  enabled: true
  direct: false  # true 时匹配到直接执行并下载
```

---

## 📡 API 概览

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | `/api/auth/*` | 登录、验证码 |
| 数据库 | `/api/databases/*` | 数据库连接 CRUD、测试连接 |
| SSH | `/api/ssh/*` | SSH 配置 CRUD |
| 查询选项 | `/api/scripts/*` | 查询/导出选项 CRUD、模板渲染 |
| 查询执行 | `/api/query/*` | 查询执行、智能匹配、SSE 状态 |
| 导出执行 | `/api/export/*` | 导出执行 |
| 自动导出 | `/api/auto-export/*` | 自动导出任务 CRUD |
| 用户 | `/api/users/*` | 用户 CRUD、管理员设置用户头像 |
| 角色 | `/api/roles/*` | 角色 CRUD、权限分配 |
| 日志 | `/api/logs/*` | 登录日志、操作日志查询与清空 |
| AI | `/api/ai/*` | AI 模型、技能、对话 |
| Agent | `/api/agents/*` | AI Agent 管理 |
| 开放 API | `/api/open-api/*` | OpenAI 兼容端点 |
| 代付流程 | `/api/pay-flow/*` | 流程模板、执行记录 |
| 工单 | `/api/tickets/*` | 工单管理 |

---

## 🛠️ 技术栈

<div align="center">

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | ![Vue](https://img.shields.io/badge/Vue-3-42b883?style=flat-square&logo=vuedotjs&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white) ![Element+](https://img.shields.io/badge/Element+Plus-2.x-409EFF?style=flat-square) | 响应式管理界面 |
| **后端** | ![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-D71F00?style=flat-square) | RESTful API 服务 |
| **数据库** | ![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat-square&logo=mysql&logoColor=white) | 元数据存储 |
| **AI** | ![OpenAI](https://img.shields.io/badge/OpenAI-兼容-412991?style=flat-square&logo=openai&logoColor=white) | 多模型支持 |
| **部署** | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![Nginx](https://img.shields.io/badge/Nginx-009639?style=flat-square&logo=nginx&logoColor=white) | 容器化部署 |

</div>

---

## 📋 SQL 模板功能

查询选项和导出选项支持 SQL 模板模式，使用 Jinja2 语法动态生成 SQL。

### 使用场景

按月分表的场景，需要查询最近 12 个月的数据并 UNION ALL：

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

### 变量来源

每个模板变量可设置「变量来源」，来源为 `param` 时可直接复用脚本「参数配置」中已定义的导出参数，由用户在查询/导出执行页填写参数值后自动注入模板变量：

| 来源 | 说明 |
|------|------|
| `auto`（配置参数生成） | 按变量类型与配置自动生成取值（如按周期生成日期列表、按默认值填充文本/数字），无需用户输入 |
| `param`（取自执行参数） | 复用脚本「参数配置」中已定义的参数：选择参数，范围参数（range）可进一步指定取「整体值 / 起始值 / 结束值」，执行时以用户填写的参数值渲染模板 |

模板变量通过 `param`（绑定的参数名）与 `param_part`（`start` / `end`，仅范围参数按起始/结束拆分时才需要）两个字段绑定参数：

- 普通参数：直接取该参数值；
- 范围参数拆分为两个变量（如「起始时间」+「结束时间」）：分别绑定同一参数的 `start` / `end`，执行时自动取日期范围拆分后的 `{参数名}_start` / `{参数名}_end` 值，
  也兼容参数值为数组或 `"开始,结束"` 字符串的形态。

执行流程为：先完成参数归一化（含日期范围拆分）→ 再用归一化后的参数渲染 Jinja2 模板 → 最后进行 `{{param}}` / `:param` 占位替换。脚本管理中预览模板时，会为「取自执行参数」的变量注入占位值，便于查看 SQL 结构。

---

## 📝 变更日志

<details>
<summary><strong>📦 v2.6.x — 多Agent协作增强</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-10-30 | v2.6.42 | 修复信息查询（lookup）脚本报"SQL配置验证失败"（含校验器两处误报与可选参数渲染缺陷）：**根因①（校验器误报-多行SQL）** `sql_validator.py` 的 `_check_basic_syntax` 中 `SELECT\s+.+\s+FROM` 正则未加 `re.DOTALL`，`.` 不跨行，导致列名换行书写的多行 SELECT 被误判"SELECT 语句缺少 FROM 子句"；**根因②（校验器误报-占位符形态）** 同一函数的 WHERE 检查与 `_extract_parameters` 只识别 `:param` 一种占位符，使用 `{{param}}` 写法的脚本被误判"WHERE 子句中缺少参数占位符"——两项叠加使 `LookupService.execute_lookup` 第 69 行对原始 `sql_text` 的校验直接失败并返回"SQL配置验证失败，请联系管理员"。修复：正则加 `re.DOTALL`；WHERE 占位符检查与参数提取统一兼容 `:param` 与 `{{param}}` 两种形态（回归用例验证无 FROM / 无占位符 / 多语句 / 注释 / 引号不匹配 / UNION 注入仍被拦截，未放宽安全边界）；**根因③（lookup 引擎不支持 Jinja2 控制结构）** lookup 链路直接校验并执行原始 `sql_text`，`_replace_placeholders` 仅做 `{{param}}` 文本替换（自动包裹单引号并转义），**不渲染** `{% if %}` / `{%- set -%}` 等 Jinja2 控制结构——Jinja2 模板写法（仅查询/导出脚本的 `sql_template` 支持）会把这些标签原样发给 MySQL 造成语法错误；且 `{{param}}` 由替换器自动加引号，SQL 中切勿再手动包单引号（否则渲染出 `''value''` 双引号字面量同样报语法错误）；**根因④（可选条件缺参即残留字面量）** 前端 `AiChat.vue` 与 AI 链路只传**非空**参数，`_replace_placeholders` 原先对未传参数原样保留 `{{param}}`。修复：未传参数按空字符串 `''` 渲染，从而支持 `({{param}} = '' OR col = {{param}})` 可选过滤条件写法——不传该参数时条件恒真不过滤，传入时按值过滤。信息查询脚本推荐写法：``WHERE 1 = 1 AND ({{id_card}} = '' OR mi.id_card = {{id_card}}) AND ({{channel_merchant_no}} = '' OR m.`code` = {{channel_merchant_no}})`` |
| 2026-10-30 | v2.6.43 | 信息查询（lookup）脚本支持 Jinja2 语法：**功能** `sql_text` 含 `{% %}` / `{# #}` 控制语法即自动进入 Jinja2 模板模式（完整 Jinja2 语义：`{% if %}` 可选条件、`{% set %}` 变量、`{% for %}` 循环、`| trim`/`| default`/`| join` 等过滤器、辅助变量 `now`/`today`/`current_month`/`current_year`）；不含控制语法的旧脚本沿用原有 `{{param}}` 自动加引号语义，两种模式按内容自动判别、互不影响（53 项断言实测：用户原始 Jinja SQL 四种参数组合全部渲染正确、旧写法回归无变化、注入拦截不放松）。**实现** ① `sql_template.py` 新增共享函数 `has_jinja_syntax`（模式检测）、`render_jinja_structure`（占位值结构渲染，校验/预览用）、`render_jinja_with_params`（真实值渲染，`finalize` 钩子做 SQL 值安全化——单引号 `''` 化转义、`None`→`''`、`bool`→`1`/`0`、list→逗号拼接；**不自动加引号**，引号由 SQL 作者手写如 `'{{ id_card }}'`，与查询/导出脚本的 `sql_template` 语义对齐）；② `lookup_service.py` 重构 `execute_lookup`——参数映射提前到渲染之前（Jinja context 需要映射后的参数名），Jinja 模式先"占位值结构渲染 + 校验"（避免参数值中的 `; -- union select` 触发注入模式误报，校验的是模板结构而非参数值）再"真实值渲染执行"，模板解析/渲染失败返回"SQL配置验证失败，请联系管理员"；③ `sql_validator.py` 的 `validate()` 新增 `allow_inline_params` 参数——为 True 时跳过"未检测到查询参数"警告与"WHERE 子句中缺少参数占位符"检查（参数已内联），危险关键字/注入模式/括号引号匹配/FROM 检查照常；④ 修复 `_extract_bind_params`——先剔除单引号字符串字面量再提取 `:name`，避免内联值中的冒号（如时间 `'12:30'`、URL）被误识别为 bind 参数导致误报"缺少查询参数"；⑤ `{{param}}` 提取与替换正则放宽为容忍空格与过滤器（`{{ id_card | trim }}`）。**联动** `script_routes.py` 的两个 validate 端点（`POST /api/scripts/<id>/validate` 与 `POST /api/scripts/validate`）同步 Jinja 感知——脚本管理页"验证"按钮对 Jinja 脚本先结构渲染再校验，不再误报 |
| 2026-10-12 | v2.6.40 | 下载结果文件时对「未查询到数据」等情形给出**明确原因**，不再统一笼统提示「文件被清理或者不存在」：①（后端）`download_routes.py` 的 `/api/download/<file_id>` 细化失败分支——任务不存在、`output_file` 为空且已完成且 `total_rows=0`（**未匹配到数据，未生成结果文件**）、已完成但未生成文件、任务失败/取消（回显 `error_message`）、任务未完成、`output_file` 有值但磁盘文件已被定时清理，分别返回对应 `message`；②（前端根因）四处下载逻辑（`ExportExecutor.vue` / `QueryExecutor.vue` / `History.vue` / `Dashboard.vue`）原先用 `fetch(url, { method: 'HEAD' })` 预检，**HEAD 响应无 body**，`check.json()` 解析必然失败并回退到默认文案，导致后端即便返回具体原因也**永远显示笼统提示**；现改为 HEAD 失败时再用 GET 读取后端 `message`（仅失败路径，且此时为小体积 JSON 错误，不影响大文件下载的用户手势）；③（详情页）导出/查询执行页在 `status=completed` 且 `output_file` 为空时，用 `el-alert` 提示「本次未查询到匹配的数据，未生成结果文件」替代下载按钮，历史/仪表盘详情页下载按钮增加 `output_file` 存在性判断 |
| 2026-10-12 | v2.6.39 | 修复 AI 对话下达任务指令时系统任务/导出等**重复执行**（多重幂等加固）：根因①（后端-监督者 retry 重跑副作用）流式 `/chats/<id>/send-stream` 的监督者复核熔断条件原先只看 `any_card_created`，而**自动执行的系统任务**（`auto_executed=True`，`ai_routes.py` L2572 分支）与**监督者自动评估通过**（`_supervisor_auto_exec`，L2608 分支）两条分支都只落库不建确认卡、**未置位该标志**，于是监督者判定 `retry` 时 `continue` 重入外层循环、**重跑工具阶段**导致副作用真实执行两次并再次 `yield tool_results` 触发前端二次自动执行；修复：新增 `any_side_effect` 标志——上述两条分支及 `create_ticket` 立即建单分支（`ticket_id` 存在时）置 `True`，并将其纳入监督者熔断条件（`any_card_created or any_side_effect or request_failed`），一旦本轮已产生不可回滚副作用即禁止 retry；②（后端-请求级幂等守卫）`AiService._tool_request_system_task` 在自动执行（API/脚本）前新增基于 Flask `g` 的**请求级幂等缓存**（key = `任务ID + 任务类型 + 排序后参数JSON`），命中即直接复用上次执行结果并告警跳过，覆盖同一请求内的监督者 retry / 故障转移重入 / 链式循环重复调用 / 非流式二次回复再次执行工具（`stream_with_context` 保证同一请求含 retry 共享同一 `g`）；③（前端-自动执行幂等）`AiChat.vue` 的 `handleToolResults` 入口按 `tool_call_id` 去重（组件级 Set，超 500 清空），避免同一工具结果事件被重复处理；`doExecuteSystemTask` 补「执行中/已完成」防重守卫（与 `confirmExport` 一致，仍允许失败后重试） |
| 2026-10-12 | v2.6.38 | 修复自动导出「下次执行时间」显示多出 8 小时：根因是创建/更新路由与调度器**存储口径不一致**——调度器 `_check_and_execute` 按北京时间算出后用 `astimezone(timezone.utc)` 存 **naive UTC**，而路由 `auto_export_routes.py` 的 create/update 用 `croniter(cron_expr).get_next(datetime)`（未传起始时间，以**本机朴素时间**为基准）得到的是**北京墙钟时间**却未做时区转换直接落库；展示层 `AutoExportTask.to_dict` 统一用 `beijing_isoformat`（按 UTC 再 +8）输出，于是路由写入的 `10:00` 被当成 UTC 又 +8 → 列表显示 **18:00**（如「每季度首月 7 日 10:00」Cron `0 10 7 1,4,7,10 *` 显示为 2027-01-07 18:00:00）。修复：新增共用函数 `compute_next_run_at(cron_expr, shift=False)`（按北京时间取 `get_next`，顺移后统一 `astimezone(timezone.utc)` 转 naive UTC），调度器与创建/更新路由全部改用它，杜绝两条路径口径再次错位；同时移除路由中因此不再使用的 `datetime` / `shift_to_next_workday` 导入 |
| 2026-10-12 | v2.6.37 | 修复自动导出邮件通知彻底不触发（完成回调链路断裂）：根因是 `_execute_auto_task` 挂载的完成回调 `on_complete=lambda tid, tstatus: _on_export_complete(app, auto_task.id, tid, tstatus)` **在 lambda 内延迟读取 `auto_task.id`**——回调须等后台导出线程跑完（数秒~数分钟）才执行，届时调度器 `_check_and_execute` 的 app 上下文早已退出、session 被 `db.session.remove()` 分离，且循环末尾的 `db.session.commit()` 又把实例 expire，于是读取 `auto_task.id` 抛 `DetachedInstanceError`；该异常随即被 `_execute_export_background` 中包裹回调的 `except Exception: pass` 静默吞掉，回调**从未进入** `_on_export_complete`——邮件不发送、执行日志无任何「邮件通知」记录、应用日志亦无痕（这正解释了 v2.6.36 补齐日志后仍「看不到任何记录」）。修复：① 调用前**提前取出** `auto_task_id = auto_task.id`（纯整数），lambda 仅引用该局部变量，彻底切断对已分离 ORM 实例的延迟访问；② 新增 `_invoke_on_complete` 统一封装回调调用，回调异常改为记录 error 日志（含 `exc_info`），不再 `pass`；③ `_notify_log` 写执行日志失败时同样记录错误并 `rollback`；④ `_on_export_complete` 入口新增「导出完成回调触发」info 日志，便于在应用日志中确认回调是否真正执行 |
| 2026-10-12 | v2.6.36 | 自动导出邮件通知日志写入任务执行日志（排查漏发）：`send_auto_export_notification` 内部新增 `_notify_log` 辅助函数，将邮件通知全链路关键节点——任务未启用通知、SMTP 主机/账号/密码未配置、通知邮箱为空、附加文件就绪/附件文件不存在、连接 SMTP（主机端口发件人收件人）、部分收件人被拒绝、发送成功、发送失败（含异常详情）——在写应用日志的同时同步追加到导出任务执行日志（`query_task.logs`，前端任务详情执行日志中可见，自动执行与手动重发均覆盖）；`_on_export_complete` 完成回调自身处理失败时也向任务执行日志补写 error 记录（`query_task` 为 None 的触发失败路径仅写应用日志）。修复此前"自动导出未收到邮件时执行日志中无任何邮件相关记录、无法定位卡点"的问题 |
| 2026-10-11 | v2.6.35 | 自动导出任务 Cron 快捷设置 + 遇非工作日顺移：① 配置页「Cron表达式」新增**快捷设置下拉**（每天08:00/每天00:00/每周一08:00/每月1日08:00/**每季度首月7日10:00**/每年1月1日00:00），选择后自动填入表达式，仍保留手写输入框供微调；② 新增「遇非工作日顺移」开关（`shift_to_next_workday`）——标准 Cron 无法表达「遇休息日顺延」，故在调度层补偿：任务开启后，调度器与创建/更新接口在按 Cron 算出计划时间（上次/下次触发）后，若落在**周六/周日**则向后顺移到**下一个周一**（保持时分不变）再参与触发判断与 `next_run_at` 展示；③ 模型 `AutoExportTask` 新增列 `shift_to_next_workday`（默认 False），经 `_auto_migrate` 自动加列并同步 `database/init.sql`；创建/更新路由白名单接入该字段；④ 说明：本例「每季度首月第 7 天上午 10 点」本身即可用标准 Cron `0 10 7 1,4,7,10 *` 表达，预设下拉已内置该表达式 |
| 2026-10-11 | v2.6.34 | 修复自动导出任务邮件通知漏发且无任何反馈（可观测性缺陷）：① `send_auto_export_notification` 原实现将「任务未启用通知/SMTP 主机/账号/密码未配置/通知邮箱为空」等前置条件不满足以及整段发送逻辑的所有异常**全部静默 return/吞掉**，导致「已开启邮件通知和附件发送却未收到邮件」时系统无任何日志与提示可查；现改为统一返回 `(success, message)`，前置条件不满足返回明确的失败原因文案，发送过程异常以 `exc_info=True` 记录完整堆栈；② 修改本地导出完成的回调 `_on_export_complete`——原先裸调用通知函数、异常同样被上层静默丢弃，现包裹 try/except 并消费返回值，未完成/失败时写入 warning/error 日志（含自动导出任务名与失败原因）；③ 修复 `/api/auto-export/<id>/resend-email`「重发邮件」接口两处缺陷——接口内引用了**未定义的 `logger`**（一进入错误分支即 `NameError`）、且无论发送结果如何都无条件返回成功；现补 `import logging` 与模块级 `logger`，并按通知函数真实返回值返回（失败时 HTTP 500 + 具体原因，成功时记录操作日志），彻底消除「操作了却如石沉大海」的迷惑 |
| 2026-10-11 | v2.6.33 | 自动导出任务时间范围参数自动补全时分秒：① 后端 `resolve_auto_params` 的全部 8 个 `range_*` 动态表达式（本月/上月/本年/去年/本季/上季/近7天/近30天）解析时，除日期外补齐时分秒——`{参数}_start` 补 `00:00:00`、`{参数}_end` 补 `23:59:59`，确保按整段时间查询时结尾当天数据不被漏掉；② 前端自动导出任务配置页「自定义固定值」范围选择器由 `daterange`（`YYYY-MM-DD`）升级为 `datetimerange`（`YYYY-MM-DD HH:mm:ss`，配 `default-time` 起始 `00:00:00`/结束 `23:59:59`），与手动导出页（v2.6.29）保持一致；③ 范围动态表达式预览文案同步显示补全后的时分秒；④ 修复编辑任务时「自定义固定值」范围无法回填的问题（保存时拆分为 `{参数}_start`/`{参数}_end`，回填时重新组装为数组，并对历史仅日期数据自动补时分秒） |
| 2026-10-10 | v2.6.32 | 修复导出列名预览不随用户参数动态变化（动态 SQL 别名未生效）：导出预览列名与最终表头在模板脚本（动态 SQL）场景下**重新渲染了一次模板却未传入导出参数**，导致「变量来源=`param`」（取自执行参数）的模板变量取不到用户在导出页填写的值，别名保持静态（如 `` `{{ period }}新增商户数` `` 恒显示为 `新增商户数`）。现改为直接复用 `_prepare_script_sql` 返回的**已按导出参数完成渲染与占位替换**的最终 SQL 提取列名——`preview_columns`（预览）与 `_execute_export_background`（实际导出表头）均不再二次渲染，使表头随用户填写的参数动态变化，并保证预览与实际导出一致 |
| 2026-10-10 | v2.6.31 | 修复导出列名解析无法识别反引号/引号包裹的别名：`SQLValidator.extract_column_names` 提取别名时原正则 `\s+AS\s+(\w+)$` 与 `\s+(\w+)$` 仅支持裸标识符，遇到 MySQL 反引号引用的别名（如 `` AS `2026年的10-10月新增商户数` ``、`` `...交易金额(单位: 元)` ``）匹配失败，导致该列退化为 `CASE`/`SUM` 等函数关键字名；现统一引入标识符模式，兼容反引号 `` `name` ``、双引号 `"name"`、单引号 `'name'` 及裸 `name` 四种别名形式（同时覆盖 AS 别名、无 AS 别名、`IF()`/`IFNULL()` 剩余别名），使含中文、括号、空格、连字符的复杂别名均能正确解析 |
| 2026-10-10 | v2.6.30 | 导出执行前自动预览 SQL 解析列名：导出执行页进入第 3 步「执行导出」时自动请求后端解析列名并展示，供用户核对表头后再执行。① 后端将 `_execute_export_background` 中「参数归一化 + 日期范围拆分 + 全部/neq/多值处理 + SQL 模板渲染」逻辑抽取为可复用的静态方法 `ExportService._prepare_script_sql`，供预览与实际执行共用，保证预览列名与最终导出表头一致；② 新增 `ExportService.preview_columns` 服务方法（复用同一归一化逻辑 + `SQLValidator.extract_column_names`，不访问数据库）与路由 `POST /api/export/preview-columns`（复用登录鉴权与 `type=='export'` 校验，返回 `[{script_id, script_name, columns, error}]`）；③ 前端 `api.export.previewColumns` 新增接口，`ExportExecutor.vue` 将执行参数构建抽取为 `buildExportParamsValues` 并与预览共用，进入第 3 步自动加载、展示每个导出选项解析出的列名（带序号标签、列数统计），对模板渲染失败/解析失败给出提示，并附「列名由 SQL 自动解析、复杂语句可能存在偏差」的核对提示 |
| 2026-10-10 | v2.6.29 | 时间范围参数默认时分秒 + 数据库连接韧性增强（修复长查询报错）：① 导出执行页时间范围参数（datetime 类型）增加 `default-time`，选择日期后起始时间默认 `00:00:00`、结束时间默认 `23:59:59`；② 修复导出的长查询在 60 秒左右报 `(pymysql.err.InternalError) Packet sequence number wrong - got 45 expected 0`——根因是 pymysql 连接级 `read_timeout`/`write_timeout` 硬编码为 60 秒，长查询被 socket 超时掐断后连接残留响应包被污染；现将 socket 超时改为可配置 `socket_timeout`（默认 300 秒），并在执行前按查询超时自动提升（`_ensure_socket_timeout`，不足则 dispose 连接池重建）；③ 将 `packet sequence`/`malformed packet`/`out of sync` 等纳入连接错误识别，触发自动 `_reconnect` 重试；④ 查询执行/批量查询均改为「重试外壳 + 单次执行」，出错时 `connection.invalidate()` 废弃被污染连接、确保游标 `result.close()`；⑤ 重构 `get_connection`（拆分为 `_connect_with_retry` + 单次 yield），消除 contextmanager 重复 yield 导致的 `generator didn't stop after throw()` 隐患 |
| 2026-10-10 | v2.6.28 | SQL 模板变量改为直接复用「参数配置」（修正 v2.6.27 方向）：① 脚本管理模板变量「变量来源」由「配置参数生成/用户执行时填写」调整为「配置参数生成/取自执行参数」——来源=`param` 时选择已有参数，范围参数可再指定取「整体值/起始值/结束值」，并以 `param`/`param_part` 绑定；② 后端 `render_sql_template` 新增 `export_params` 入参与 `_resolve_param_value` 解析（普通参数直接取值，范围参数支持 `{参数名}_start`/`{参数名}_end` 拆分取值，兼容数组与逗号字符串），导出执行流程调整为「参数归一化（含日期范围拆分）→ 渲染模板 → 占位替换」，使模板变量直接引用用户在导出页填写的参数；③ 移除查询执行页与导出执行页此前新增的独立「模板变量（执行时填写）」输入区及相关逻辑，统一走「参数配置」；④ `get_template_preview` 预览时为「取自执行参数」变量注入占位值，避免预览因缺少运行参数而报错 |
| 2026-10-10 | v2.6.27 | SQL 模板变量支持「用户执行时填写」：① 脚本管理模板变量新增「变量来源」选择（配置参数生成 / 用户执行时填写），来源为"用户填写"的变量显示"执行时填写"标签，配置区简化为提示文案(placeholder)+默认值(不填则执行时必填)；② 查询执行页（第3步）与导出执行页（第2步）新增"模板变量（执行时填写）"分组输入区，按脚本分组展示、无默认值自动标记必填并校验、数字类型自动转换、预留默认值可留空；③ 后端打通模板变量传递全链路：`get_template_preview` 预览支持传入参数，查询/导出执行与重试接口均接收 `template_params`（按脚本分组 `{scriptId:{变量:值}}`，兼容扁平结构，新增 `resolve_script_template_params` 解析），重试任务携带当前填写的模板变量重新执行 |
| 2026-09-23 | v2.6.26 | AI宠物毛绒仿真质感+五官升级修复：① 修复——10个宠物根节点补上专属类名(robot/cat/bunny/panda/bear/fox/frog/koala/pig/chick)，使v2.6.24的五官升级(眼白+瞳孔+高光)与--pet-ink个性瞳色真正生效（此前 .creature.cat 等分类选择器从未匹配，只有mood表情规则生效，眼睛仍是实心点）；pet-moods.css 重写，mood表情规则统一 !important 保证表情稳定压过基础五官与工作态，frog/panda 眼睛补 position:relative 防止高光错位；② 新增 pet-fur.css 毛绒/仿真质感——9只小动物统一「呼吸起伏」动画(脚底原点轻微向上生长，活体感)；头/身体用立体球形径向渐变(光源左上)替代扁平线性渐变；同色柔边光晕+内高光(顶)+内阴影(底)模拟毛绒褶皱与厚度；小猫/小熊/狐狸/熊猫/小猪/考拉/小鸡各自毛色高光，兔子雪白绒毛、小鸡鹅黄绒毛、考拉灰蓝绒毛；青蛙走光滑釉面光泽路线(高对比高光，符合两栖动物无毛特征)；兔子/小熊/熊猫补齐闲时耳朵轻微摆动(工作中由scoped接管) |
| 2026-09-23 | v2.6.25 | AI宠物「努力工作/任务完成」状态机：① 工作态聚合——hasTasks 从「仅工单」扩展为「工单指派(polling) + 对话下达任务指令(chat_start/chat_end事件)」双源，宠物对话框handleSend/断线恢复resumeActiveStream、AI助手页sendMessage/sendStreamMessage在请求开始时emit chat_start、结束时emit chat_end（含AbortError手动终止标记ok:false），工单完成靠fetchTasks前后数量diff检测；② 工作态零互动——工作中清空闲时气泡并暂停闲时排程，围观(runPeek)/闲聊/滚动/偷袭全部跳过，仅保留任务进度播报气泡轮播；③ 完成蹦起庆祝——工单清空或chat_end(ok)时宠物弹跳庆祝(WAAPI两次递减跳)+兴奋表情+「耶！任务搞定，交给我就是快⚡」等5条完成话术，2秒内刚出过文件提醒则去重跳过、手动终止不庆祝；④ 工作表情轮换——working弧线眼之上叠加focus(💪举拳加油)/think(💭思考泡泡+视线抬高)每6~11秒随机切换，闲时表情系统(happy/curious/sneaky/proud/excited/dizzy/sleepy/alert)照常，两种状态都有丰富恰当表情变化 |
| 2026-09-23 | v2.6.24 | AI宠物互动观察者+表情系统：① 新增轻量事件总线 petBus.js，查询执行页/导出执行页在任务提交时 emit operation、任务完成产出文件时 emit file_ready，AI助手页（导出/查询/分润完成）与宠物对话框（finishDone）同样接入；② 围观互动——用户手动执行查询/导出时宠物慢慢凑近屏幕（两段探头探脑靠近光标35%距离），说俏皮话（含用户点名的「主人，在干嘛呢，这么简单的活下次直接交给我吧」「啥机密数据啊，我保证不偷看哦 🙈」共10条，查询/导出/通用三组），然后快速跑回原位；30秒冷却、对话框打开/切后台/拖动/动效中自动跳过；③ 文件提醒——任何来源的查询/导出/分润任务完成生成文件后，宠物弹跳庆祝+惊喜表情+「叮！文件出炉啦，快来下载 📥」等4条提醒话术（带任务名，对话框打开时静默）；④ 表情系统——新建全局样式 pet-moods.css：8个实心点眼宠物升级为「眼白+瞳孔+高光」三层结构（frog/panda自带眼白仅补高光），每宠物保留个性瞳色（--pet-ink变量），定义8种表情（happy弯月眼/curious大眼偷瞄/sneaky眯眼坏笑+冷汗/proud闭眼咧嘴/excited大眼O嘴+星星/dizzy×眼+波浪嘴+转圈星/sleepy闭眼+呼噜泡/alert瞪眼竖瞳），表情覆盖working状态、:not(.working)守卫不破坏既有工作弧线眼；10个宠物组件统一接入mood prop，idle互动随机表情、滚动→dizzy、偷袭→sneaky→proud、围观→sneaky/curious、文件提醒→alert |
| 2026-09-23 | v2.6.23 | AI宠物空闲互动增强：互动频率从18~42秒提升到10~24秒随机（稍频繁不过度打扰）；闲聊话术库从12条扩充到30条（SQL梗/久坐提醒/监督者彩蛋/摸鱼关怀等）；纯CSS小动效新增「扭屁股小舞步」「后空翻」（共6种）；新增两种JS驱动特殊大动效（22%概率触发）——「滚动横穿屏幕」本体贴地翻滚到屏幕另一侧停顿后滚回原位（WAAPI平移+造型翻滚、气泡保持水平可读），「偷袭鼠标光标」监听mousemove记录光标位置后蓄力下蹲→弧线猛扑到光标右上方停留→蹦回原位；特殊动效专用话术5条×2，中途打开对话/切后台/拖动自动安全复位，结束自动恢复排程；卸载时清理WAAPI与事件监听 |
| 2026-09-23 | v2.6.22 | AI宠物对话框对齐页面AI助手完整能力：① SSE事件面完全对齐（心跳/深度思考/监督复核supervision/工具结果tool_results/截断/终止aborted/done含token与耗时统计）；② 监督者监督审核可视化——复核中/复核通过/要求重新生成（自动清空重流）/标记人工复核状态条+复核记录轮次展开详情，历史消息恢复后端持久化的supervision_records；③ 直接完成任务——工具确认卡片（导出/查询/系统任务/分润）参数预览、监督者评估徽标与意见、点击即执行+进度轮询+文件下载+结果反馈持久化；监督者自动评估通过（_supervisor_auto_executed）的任务自动执行；系统任务参数齐备自动执行、缺参数/多数据库时卡片内联参数表单；选项选择卡片（list_*工具）多选+按类型执行；信息查询show_all_fields结果表格（前20条）；工单创建卡片；查询任务卡片内三步上传Excel→智能匹配参数列→执行；④ 会话级增强——断线自动恢复活跃流（resume-stream）、发送可随时终止（abort）、执行状态/卡片/反馈消息全部持久化并与AI助手页双向共享 |
| 2026-09-23 | v2.6.21 | 全量操作日志埋点 + AI宠物空闲自动互动：新增全局 after_request 自动埋点中间件（对未显式埋点的写操作POST/PUT/PATCH/DELETE自动记录操作日志，含写方法过滤、静态校验类噪点黑名单、g._op_logged 请求内去重、仅记录成功响应<400）；重点操作显式埋点覆盖查询执行、导出执行、自动导出（手动运行/重发邮件）、AI对话（发起会话/发消息/流式发消息）、工单（创建/暂存草稿/提交草稿/状态流转/重启/重派/重开/转移）、登录；操作日志页 action/target 标签与筛选项大幅扩展（24种动作、27种目标，筛选项支持搜索）；AI宠物在无任务且未聊天时随机间隔（18~42秒）自动播报闲聊气泡并触发挥手/跳跃/转圈/挤压小动效（柔和底色气泡与任务播报区分，气泡展示6秒后自动收起） |
| 2026-09-23 | v2.6.20 | AI 宠物新增 10 种造型可选：个人中心「AI宠物」开关下增加造型选择卡片（实时预览，含小机器人/喵喵/兔兔/团团/棕熊/狐狐/猪猪/呱呱/考拉/小鸡）；宠物本体改为动态组件渲染，有进行中任务时头顶新增星光标识；宠物对话窗头部/空状态/消息头像随造型切换 emoji 与昵称；后端 User 新增 pet_style 字段并加白名单校验（默认 robot） |
| 2026-09-23 | v2.6.19 | AI宠物升级为弹窗直接对话：点击宠物在右下角弹出漂亮对话窗（渐变头部+迷你机器人+圆角气泡），默认自动继续最近一次会话（含历史消息加载），支持开启新对话；消息流式输出（SSE，失败自动回退非流式）、Markdown 渲染、Enter发送/Shift+Enter换行；宠物默认停靠右下角，支持拖动到任意位置（localStorage 持久化、边界防溢出），位移小于6px视为点击；移除旧的跳转 AI 助手页交互 |
| 2026-09-23 | v2.6.18 | 左下角新增 AI 宠物机器人助手：点击快捷开启 AI 新对话，头顶气泡自动轮播播报当前用户提交给 AI 的工单处理进度（等待接单/处理中/待确认等，15秒轮询、多任务6秒轮换）；个人中心新增"AI宠物"开关（默认开启）；纯 CSS 绘制可爱机器人（眨眼/悬浮/天线闪烁/工作时摇摆动画），随侧边栏折叠自适应位置 |
| 2026-09-23 | v2.6.17 | 修复管理员新建脚本后其他页面选不到：所有路由页面被 Layout keep-alive 缓存，切页时 onMounted 不再触发，导致系统任务/导出执行/自动导出/导出管理页的脚本列表停留在旧快照；为这四个页面增加 onActivated 切回自动刷新（与 AgentManager 等页面既有模式一致），管理员新建脚本后无需重新登录即可选中，普通用户授权可见逻辑不变 |
| 2026-09-23 | v2.6.16 | 修复右上角任务面板运行时长多算8小时：数据库按UTC存储时间，但 task_routes 三个归一化函数（查询任务/系统任务/工单）直接输出裸UTC时间字符串，前端按本地时间解析导致偏差；现统一改用 beijing_isoformat 序列化为北京时间，与工单详情等其他接口保持一致 |
| 2026-09-20 | v2.6.15 | 右上角任务面板运行时长级联折算：超过1天显示"几天几小时几分钟"，超过1周显示"几周几天几小时几分钟"，依次向上折算至月（30天）/年（365天），零值单位自动省略，不足1分钟仍显示"刚刚开始" |
| 2026-09-20 | v2.6.14 | 修复 AI 会话管理详情对话框头像显示错误：用户消息头像原先显示当前登录管理员头像，现按会话真实所有者渲染（get_messages 接口新增 chat_user 字段返回会话所有者的用户名/昵称/头像，无头像回退默认图标） |
| 2026-09-20 | v2.6.13 | 用户头像管理 + 审计日志：① 超级管理员可为任意用户上传/删除头像，用户列表新增头像列；② 新增登录日志（记录用户名/IP/UA/成功失败/失败原因）与操作日志（记录用户管理增删改、头像设置等操作及IP），支持分页/关键词/状态/日期筛选与一键清空 |
| 2026-09-20 | v2.6.12 | 修复大小模型协作模式两个缺陷：① 流式响应生成器内访问过期ORM对象导致 DetachedInstanceError；② 大模型推理返回0字（复杂请求触发工具调用但未执行工具闭环）。流式协作预生成现支持信息查询类工具多轮闭环执行，操作型/选择卡片类工具自动回退常规流式处理 |
| 2026-09-20 | v2.6.11 | 路由策略新增"大小模型协作"模式：大模型推理分析+小模型整理输出；简单问答小模型一步完成；支持自定义大/小模型列表，留空自动按模型名分类 |
| 2026-09-04 | v2.6.10 | 个人中心（修改昵称/性别/手机号）+ 头像上传（右上角/聊天对话框显示头像） |
| 2026-09-04 | v2.6.9 | 钉钉通知触发时机精细化 — 按指派类型区分（人工工单已处理时通知提交人核实，AI工单验收通过后通知完成） |
| 2026-09-04 | v2.6.8 | 钉钉通知模板支持 Markdown 编辑 + 实时预览（工具栏/👁预览/模板变量） |
| 2026-09-04 | v2.6.7 | 工单重启（管理员可重启已结束工单）+ 钉钉Webhook通知（指派/完成/重启通知，支持加签和模板） |
| 2026-09-04 | v2.6.6 | 系统任务 UPDATE 语句支持列表参数注入，修复 SQL 验证器误报 DDL 危险关键字 |
| 2026-09-04 | v2.6.5 | 工单涉及系统标签可点击跳转到业务系统页面；右上角进行中任务运行时间增加分钟精度并实时更新 |
| 2026-09-03 | v2.6.4 | 执行者Agent支持设置默认监督者 |
| 2026-09-03 | v2.6.3 | AI Agent感知用户角色 |
| 2026-09-03 | v2.6.2 | 修复插话发送不生效问题 |
| 2026-09-03 | v2.6.1 | 排队消息支持重新编辑；插话三种模式 |
| 2026-09-03 | v2.6.0 | AI对话排队/插话UI升级 |

</details>

<details>
<summary><strong>📦 v2.5.x — MCP市场 + 工具增强</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-09-03 | v2.5.9 | AI模型Logo适配：新增阶跃星辰和美团 |
| 2026-09-02 | v2.5.8 | 修复MCP市场两处报错 |
| 2026-09-02 | v2.5.7 | MCP市场增强：多市场源拉取 + Tab切换 |
| 2026-08-30 | v2.5.6 | 防重复执行 + 多参数适配 |
| 2026-08-30 | v2.5.5 | 新增send_email邮件发送工具 |
| 2026-08-30 | v2.5.4 | 自动导出任务支持手动重发邮件 |
| 2026-08-30 | v2.5.3 | 修复监督者自动执行+插话发送问题 |
| 2026-08-30 | v2.5.2 | AI对话支持插话/引导 |
| 2026-08-30 | v2.5.1 | 支持自动保存SKILLS/规则 + 监督者监督 |
| 2026-08-30 | v2.5.0 | 输入框支持Alt+Enter换行 |

</details>

<details>
<summary><strong>📦 v2.4.x — 多Agent协作系统</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-08-30 | v2.4.9 | 自定义复核规则权限控制 |
| 2026-08-30 | v2.4.8 | 复核证据详情可点击查看 |
| 2026-08-30 | v2.4.7 | 支持自定义复核规则 |
| 2026-08-30 | v2.4.6 | 监督者复核改为Agent级别配置 |
| 2026-08-30 | v2.4.5 | 监督者增加态度评估，鞭答执行者改正 |
| 2026-08-30 | v2.4.4 | 修复故障转移循环不退出问题 |
| 2026-08-30 | v2.4.3 | 修复确认卡片重复 + 监督者自动执行 |
| 2026-08-30 | v2.4.2 | 监督者自动评估确认卡片 |
| 2026-08-30 | v2.4.1 | AI对话体验优化 |
| 2026-08-30 | v2.4.0 | 工单多Agent协作：执行者 + 监督者 |

</details>

<details>
<summary><strong>📦 v2.3.x — 代付流程 + Headroom压缩</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-08-29 | v2.3.22 | 运营数据看板统计指标面板 |
| 2026-08-28 | v2.3.12 | 运营数据看板崩溃根治 |
| 2026-08-28 | v2.3.11 | 运营数据看板脚本统一到scripts表 |
| 2026-08-28 | v2.3.8 | 工单草稿暂存 |
| 2026-08-27 | v2.3.5 | 修复流式对话路径Headroom压缩缺失 |
| 2026-08-27 | v2.3.0 | Headroom上下文压缩 |

</details>

<details>
<summary><strong>📦 v2.2.x — 代付流程编排</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-08-27 | v2.2.9 | 修复汇总通知邮件HTML标签不渲染 |
| 2026-08-27 | v2.2.8 | 修复批次明细展开不显示问题 |
| 2026-08-27 | v2.2.7 | 修复批次列表API 500错误 |
| 2026-08-27 | v2.2.6 | 代付流程执行记录改为批次聚合视图 |
| 2026-08-27 | v2.2.5 | 彻底修复节点重复执行问题 |
| 2026-08-26 | v2.2.4 | 流程走势图改为横向排列 |
| 2026-08-26 | v2.2.1 | 代付流程编排增强 |
| 2026-08-26 | v2.2 | 代付流程编排系统 |

</details>

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star 支持一下！⭐**

Made with ❤️ by Xiaomi LLM Core Team

</div>
