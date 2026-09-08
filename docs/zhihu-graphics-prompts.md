# 🎨 主稿 #1 配图 · AI 提示词文档

> **用途**：把以下 prompt 直接喂给 Midjourney / Stable Diffusion / DALL-E 3 / 即梦 / 通义万相等
> **已生成**：`docs/images/` 目录下 3 张（用 mcode-tools 生成，可直接用）
> **本文件**：完整的 8 张图 prompt + 制作指南

---

## 📊 8 张图分类

| # | 图片 | 类型 | AI 生成效果 | 推荐工具 |
|---|---|---|---|---|
| 1 | 头图（3 步流程） | 示意图 | ⭐⭐⭐⭐⭐ 已生成 | MJ / SD / DALL-E |
| 2 | 3 人小组 | 示意图 | ⭐⭐⭐⭐⭐ 已生成 | MJ / SD / DALL-E |
| 3 | 3 次被拉黑（聊天截图） | 仿微信截图 | ⭐⭐ | 微信对话生成器（更专业） |
| 4 | 拖拽上传界面 | 产品截图 | ❌ 必须真实截图 | 项目实跑 |
| 5 | 智能匹配 + 直通模式 | 产品截图 | ❌ 必须真实截图 | 项目实跑 |
| 6 | Dashboard 仪表盘 | 产品截图 | ❌ 必须真实截图 | 项目实跑 |
| 7 | SQL 模板 | 代码截图 | ⭐⭐⭐ | Carbon（专业） |
| 8 | 流程走势图 | 示意图 | ⭐⭐⭐⭐⭐ 已生成 | MJ / SD / DALL-E |

---

## 🖼️ 图 1 · 头图（3 步流程）

### 用途
知乎 / 公众号封面，3 步直观展示产品价值：上传 → 查 → 下载

### 通用 Prompt（英文版，跨模型通用）

```
A modern flat illustration for SaaS marketing, showing a 3-step horizontal workflow on a clean light gray background:
Step 1) An Excel file with green upload arrow uploading into cloud
Step 2) A glowing cloud database in the center with a subtle AI brain icon
Step 3) A downloaded Excel file with a green checkmark
Connected by dotted arrows with flowing particles.
Color palette: primary blue #2D7FF9, accent orange #FF8A3D, success green #34D399, soft white cards with rounded corners.
Style: clean modern SaaS marketing illustration, soft shadows, professional, no text no logo.
```

### 各模型适配版

**Midjourney**（加 v6 风格）：
```
/imagine prompt: A modern flat illustration for SaaS marketing, showing a 3-step horizontal workflow: Excel upload to cloud, cloud database with AI brain, downloaded Excel with checkmark. Connected by dotted arrows. Blue #2D7FF9, orange #FF8A3D, green #34D399 palette. Clean light gray background. Soft shadows, professional, no text no logo. --ar 16:9 --v 6 --style raw --s 50
```

**Stable Diffusion**（负面提示）：
```
正面: A modern flat illustration, SaaS marketing style, 3-step horizontal workflow, Excel upload, cloud database with AI brain icon, downloaded Excel with checkmark, dotted arrows, blue orange green palette, clean background, soft shadows, professional, no text no logo
负面: text, watermark, signature, blurry, low quality, realistic, photo, 3d render, complex details
Steps: 30, CFG: 7, Sampler: DPM++ 2M Karras, Aspect: 16:9
```

**DALL-E 3**（直接用通用版即可）：
```
A modern flat illustration for SaaS marketing, showing a 3-step horizontal workflow on a clean light gray background: Step 1) An Excel file with green upload arrow uploading into cloud, Step 2) A glowing cloud database in the center with a subtle AI brain icon, Step 3) A downloaded Excel file with a green checkmark. Connected by dotted arrows with flowing particles. Color palette: primary blue #2D7FF9, accent orange #FF8A3D, success green #34D399, soft white cards with rounded corners. Style: clean modern SaaS marketing illustration, soft shadows, professional, no text no logo. Aspect ratio 16:9.
```

**国产工具**（即梦 / 通义万相 / 文心一格）：
```
现代扁平风格插画，SaaS营销风格，3步水平工作流：第一步Excel文件绿色上传箭头进入云端，第二步中央发光的云数据库带AI大脑图标，第三步下载的Excel带绿色对勾。虚线箭头连接带流动光点。配色：主蓝#2D7FF9、橙色#FF8A3D、成功绿#34D399、白色圆角卡片。浅灰背景，柔和阴影，专业感，无文字无logo。
```

---

## 🖼️ 图 2 · 3 人小组（业务 + 研发 + DBA）

### 用途
体现"团队"和"角色分工"，呼应文章"我们决定做这个产品"章节

### 通用 Prompt
```
Three flat illustration characters standing in a row, each inside a colored circular badge:
1) A business person in blue badge holding a document and laptop
2) A developer in orange badge with code symbols on floating screen
3) A database administrator in green badge with database cylinder icon
Below them a subtle horizontal connecting line with three small icons (chart, code, database).
Background clean white.
Style: minimal flat vector illustration, professional SaaS team illustration, modern corporate style, no text, no logo.
```

### Midjourney 版
```
/imagine prompt: Three flat illustration characters in a row, each in a colored circle: business person with laptop (blue), developer with code (orange), database admin with database cylinder (green). Below a connecting line with chart-code-database icons. Clean white background. Minimal flat vector, professional SaaS team, no text no logo. --ar 16:9 --v 6 --style raw
```

### 国产工具版
```
三个扁平风格插画人物并排站立，每个在彩色圆形徽章内：1）蓝色徽章里的商务人员拿着文件和笔记本电脑，2）橙色徽章里的开发者带着浮动代码屏，3）绿色徽章里的数据库管理员带着数据库圆柱图标。下方一条细连接线配三个小图标（图表/代码/数据库）。白色干净背景。极简扁平矢量插画，专业SaaS团队风格，现代企业感，无文字无logo。
```

---

## 🖼️ 图 3 · 3 次被拉黑（故事化聊天截图）

> ⚠️ **AI 生成聊天截图效果一般**，强烈建议用专业工具：

### 推荐工具（按推荐度）

1. **🥇 微信对话生成器（在线）**
   - 网址：weixindialogue.com / klpbbs.com/wxchat
   - 优点：完全仿微信界面、支持自定义头像/昵称/时间/已读
   - 缺点：免费版有水印

2. **🥈 创客贴「微信聊天」模板**
   - 网址：chuangkit.com
   - 优点：模板多、可商用
   - 缺点：要会员

3. **🥉 Figma 手画**
   - 完全可控，但要花 30-60 分钟
   - 推荐用 Material Design 风格的 chat bubble

### 三张聊天截图文案（直接复制）

**截图 1：第一次被拉黑（白天）**
```
时间：14:32
我：在吗？能帮我导个华东区上个月销售数据吗
我：麻烦了，谢谢🙏
我：今天能给我吗？
我：……

[时间跳转 18:00]
我：哥？在吗
[已读 ✓✓]
```

**截图 2：第二次被拉黑（凌晨）**
```
时间：02:14
我：哥，帮我看个 SQL 怎么写呗
我：SELECT ... WHERE ...
我：[代码截图]
我：这个是不是漏了 JOIN 啊？

时间：02:19
李工（开发）：睡了
李工（开发）：明早再说
```

**截图 3：第三次被拉黑（群里）**
```
时间：10:15
李工（开发）：@我 哥
李工（开发）：真不是不愿意帮
李工（开发）：主要是这事本来就该有个系统解决
李工（开发）：我们再这么互相消耗
李工（开发）：谁也干不好自己的活
```

---

## 🖼️ 图 4-6 · 产品截图（必须真实截图）

> ⚠️ **AI 生成不了真实产品界面**，必须从项目实跑截取

### 截图操作步骤

#### 前置准备
1. 启动项目：
   ```bash
   cd backend
   python run.py
   # 另起一个 terminal
   cd frontend
   npm run dev
   ```
2. 打开 `http://localhost`
3. 用 `admin / admin123` 登录

#### 图 4：拖拽上传界面
- 进入「查询执行」页面
- 把鼠标移到 Excel 上传区域
- **截屏（Windows: Win+Shift+S）**
- 关键区域：上传按钮 + "把 Excel 拖到这里" 提示

#### 图 5：智能匹配 + 直通模式
- 选一个测试文件（如「华东区销售月度报表_202509.xlsx」）
- 系统自动推荐查询选项
- 打开「直通模式」开关
- **截屏** 整个上半部分

#### 图 6：Dashboard 仪表盘
- 点击「Dashboard」进入仪表盘
- 等数据加载完成
- **截屏** 完整页面

### 截图后处理

1. 用 **Figma / Canva** 加红框标注关键区域
2. 加箭头指向核心功能
3. 配色与正文主题保持一致

---

## 🖼️ 图 7 · SQL 模板（代码截图）

> ⚠️ AI 生成代码效果一般，建议用 **Carbon.now.sh**（专业）

### 推荐工具
1. **🥇 Carbon（carbon.now.sh）**
   - 最美代码截图工具
   - 支持语法高亮、主题、字体定制
   - 一键导出 PNG

2. **🥈 Polacode（VSCode 插件）**
   - VSCode 内直接生成漂亮代码图

3. **🥉 Snipaste + 暗色主题 VSCode**
   - 最低成本方案

### 代码内容（直接复制）

```sql
-- 月度销售数据查询模板
-- {{ month }} 会自动替换为 "202501" / "202502" / ...

SELECT
    order_id,
    customer_name,
    amount,
    created_at
FROM orders_{{ month }}
WHERE status = 'completed'
  AND region = 'east'
  AND created_at BETWEEN '{{ start_date }}' AND '{{ end_date }}'

UNION ALL

-- 12 个月汇总
{% for m in months %}
SELECT * FROM orders_{{ m }}
{% if not loop.last %}UNION ALL{% endif %}
{% endfor %}
```

### Carbon 导出设置
- 主题：`One Dark` / `Dracula` / `Monokai`
- 字体：`JetBrains Mono` / `Fira Code`
- 背景色：`#1E1E1E`（深色）或 `#FFFFFF`（浅色）
- 导出尺寸：2x（高清）

---

## 🖼️ 图 8 · 流程走势图（5 节点）

### 用途
体现"流程可视化"亮点，展示每个节点状态

### 通用 Prompt
```
A horizontal process flow infographic with 5 rounded rectangle nodes connected by solid green arrows, flowing left to right. Each node has a colored status circle on top: nodes 1-5 all show green checkmark, indicating all completed successfully. The nodes represent a workflow: data extraction, Excel writing, email sending, supervisor review, flow complete. Connections are solid green curved arrows with subtle motion. Background clean white with light gray node shadows. Style: clean modern process flow diagram, flat design, SaaS dashboard look, professional infographic, no text labels, aspect ratio 21:9 wide horizontal banner.
```

### Midjourney 版
```
/imagine prompt: A horizontal process flow diagram, 5 rounded rectangle nodes with green checkmark badges on top, connected by solid green curved arrows flowing left to right. Each node has subtle shadow. Clean white background. Modern flat design, SaaS dashboard look, professional infographic, no text. --ar 21:9 --v 6 --style raw
```

### 国产工具版
```
水平流程信息图，5个圆角矩形节点由实心绿色箭头从左到右连接，每个节点顶部有绿色对勾状态徽章，5个节点代表完整工作流：数据抽取、Excel写入、邮件发送、监督者审核、流程完成。连接是实心绿色弧形箭头带微妙动效。白色干净背景，节点带浅灰阴影。清爽现代流程图，扁平设计，SaaS仪表盘风格，专业信息图，无文字标签，超宽横幅21:9。
```

---

## 🎨 三类 AI 工具效果对比

| 工具 | 风格控制 | 中文支持 | 商用 | 价格 |
|---|---|---|---|---|
| **Midjourney v6** | ⭐⭐⭐⭐⭐ | 一般 | ✅ | $10/月起 |
| **DALL-E 3** | ⭐⭐⭐⭐ | ✅ | ✅ | ChatGPT Plus $20/月 |
| **Stable Diffusion** | ⭐⭐⭐⭐⭐ | ✅ | ✅ | 本地免费 / 在线平台 |
| **即梦（字节）** | ⭐⭐⭐⭐ | ✅ | ✅ | 有免费额度 |
| **通义万相（阿里）** | ⭐⭐⭐ | ✅ | ✅ | 有免费额度 |
| **mcode-tools**（本次用的）| ⭐⭐⭐ | 一般 | ✅ | 已生成 3 张可商用 |

> 💡 **建议策略**：
> - **快速用**：直接用 mcode-tools 生成的 3 张（已在 `docs/images/`）
> - **精修用**：用 MJ/SD 重新生成，调出更符合你品牌调性的版本
> - **二次创作**：用 MJ 生成的图当 input_url，做 image-to-image 微调

---

## 📦 已生成的文件清单

```
docs/
├── images/
│   ├── zhihu-cover-3step.png      ← 图 1 头图（已生成）
│   ├── zhihu-team-3people.png     ← 图 2 三人小组（已生成）
│   └── zhihu-flow-chart.png       ← 图 8 流程走势图（已生成）
└── zhihu-graphics-prompts.md      ← 本文件（完整 prompt 文档）
```

---

## ⏱️ 制作总时间估算

| 任务 | 时间 |
|---|---|
| 3 张 AI 生成的图（已就绪） | 0 min |
| 3 张聊天截图（用微信生成器） | 20-30 min |
| 3 张产品截图（启动项目实跑） | 15-20 min |
| 1 张代码截图（用 Carbon） | 5 min |
| **总计** | **40-55 min** |

> 💡 比原方案节省了 1.5-2 小时（AI 生成 3 张图省了 1-1.5h）。
