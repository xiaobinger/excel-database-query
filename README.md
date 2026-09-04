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
  <img src="https://img.shields.io/badge/version-2.6.4-blue?style=flat-square" alt="version" />
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
<td width="33%">

**🧠 多 Agent 协作**

执行者负责执行工单任务，监督者审查结果并打分（0-100），循环协作直到验收通过。

- 最大协作轮数可配置（1-20 轮）
- 监督者可授权「确认执行」
- 协作日志时间线展示

</td>
<td width="34%">

**🗜️ Headroom 上下文压缩**

智能识别内容类型，应用针对性压缩策略：

| 内容类型 | 策略 | 节省率 |
|---------|------|--------|
| JSON 数组 | SmartCrusher | 70-90% |
| 日志 | LogCompressor | 85-95% |
| 代码 | CodeCompressor | 40-70% |
| 文本 | TextCrusher | 30-60% |

</td>
<td width="33%">

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
| 用户 | `/api/users/*` | 用户 CRUD |
| 角色 | `/api/roles/*` | 角色 CRUD、权限分配 |
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

---

## 📝 变更日志

<details>
<summary><strong>📦 v2.6.x — 多Agent协作增强</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
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
