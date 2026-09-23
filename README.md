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
  <img src="https://img.shields.io/badge/version-2.6.11-blue?style=flat-square" alt="version" />
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

---

## 📝 变更日志

<details>
<summary><strong>📦 v2.6.x — 多Agent协作增强</strong></summary>

| 日期 | 版本 | 内容 |
|------|------|------|
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
