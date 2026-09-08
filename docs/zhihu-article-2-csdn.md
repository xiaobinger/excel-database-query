# AI Agent 实战：我做了个双 Agent 协作系统，一个干活的，一个挑刺的

> **项目地址**：[excel-database-query](https://github.com/yourname/excel-database-query) ⭐ Star 求支持
> **技术栈**：Python 3.10+ / Flask / Vue 3 / OpenAI 兼容 API / SQLAlchemy
> **本文配套源码**：仓库 `backend/app/services/ai_service.py` + `agent_routes.py`

---

## 一、问题：AI 输出为什么不稳定？

做 AI 应用这一年，我被 AI 坑过 3 次——

- 第一次：让 AI 写 SQL，`SELECT *` + 没 LIMIT + 没时间上界，**生产库锁了 15 分钟**
- 第二次：让 AI 算 GMV，两次问同一个问题**给了两个不同数字**（用的表不一样）
- 第三次：让 AI 配代付流程，**漏了"金额 > 5 万必须人工审核"规则**，上线 2 周才发现

**这 3 个问题的共性是：AI 干完活，没人验收。**

我尝试过加人工 review，但**业务一忙就漏，漏一次就翻车一次**。

直到我想明白一件事——**既然 AI 能干活，那它也应该能 review 别人的活。**

于是做了个**双 Agent 协作系统**：
- **执行者 Agent**：埋头干活
- **监督者 Agent**：review 执行者的结果，不满意就"打回重做"

---

## 二、整体架构

```
┌────────────────────────────────────────────────────────────┐
│                    双 Agent 协作系统架构                       │
└────────────────────────────────────────────────────────────┘

  用户任务
     │
     ▼
  ┌──────────┐         submit result         ┌──────────────┐
  │  执行者   │ ────────────────────────────▶ │   监督者     │
  │  Agent   │ ◀──────────────────────────── │   Agent     │
  │          │        feedback & score        │              │
  └──────────┘                                └──────────────┘
     │                                              │
     │  返工（score < 80）                            │
     └──────────────────────────────────────────────┘
     │
     ▼
  任务完成（score ≥ 80）
```

**核心流程**：
1. 执行者接收任务，开始干活
2. 执行者提交结果给监督者
3. 监督者逐项审查，按 0-100 打分
4. **score < 80**：连同反馈意见一起打回，执行者返工
5. **score ≥ 80**：任务通过

**默认 3 轮返工上限**（工单级可配置）。监督者还可以被授权"确认执行"——工单进入"待确认"时，监督者直接拍板，无需人工介入。

---

## 三、监督者 Agent 核心实现

### 3.1 评分维度设计

监督者不是简单打分，而是**多维度评估**：

```python
# backend/app/services/ai_service.py
SCORING_DIMENSIONS = {
    "completeness": {
        "weight": 0.3,
        "criteria": "任务的所有子需求是否都被满足？"
    },
    "accuracy": {
        "weight": 0.3,
        "criteria": "输出数据是否准确？有无错误计算？"
    },
    "compliance": {
        "weight": 0.2,
        "criteria": "是否遵守用户/系统的规则（如金额上限、风控规则）？"
    },
    "efficiency": {
        "weight": 0.2,
        "criteria": "执行路径是否最优？有没有冗余调用？"
    }
}

def calculate_final_score(dimension_scores: dict) -> int:
    """加权计算最终分数"""
    total = sum(
        dimension_scores[dim] * SCORING_DIMENSIONS[dim]["weight"]
        for dim in dimension_scores
    )
    return int(total)
```

### 3.2 监督者评审 Prompt 模板

```python
SUPERVISOR_REVIEW_PROMPT = """
你是一个严格的 AI 监督者（Supervisor Agent）。
你的任务是审查执行者（Executor Agent）提交的工作结果，并决定是否通过。

【待审查任务】
{task_description}

【执行者提交的结果】
{executor_output}

【评分维度】（每项 0-100 分）
1. completeness（30%）：任务的所有子需求是否都被满足？
2. accuracy（30%）：输出数据是否准确？有无错误计算？
3. compliance（20%）：是否遵守规则（金额上限、风控、合规）？
4. efficiency（20%）：执行路径是否最优？有没有冗余调用？

【强制检查项】（任何一项不满足 = 整体不通过）
- 涉及金额、SQL、删除操作的，必须有二次确认或限制
- 涉及用户隐私的字段，必须脱敏
- 涉及生产库的写入操作，必须有审计日志

【输出格式】（严格按 JSON）
{
  "scores": {
    "completeness": 0-100,
    "accuracy": 0-100,
    "compliance": 0-100,
    "efficiency": 0-100
  },
  "overall_score": 0-100,
  "passed": true/false,
  "issues": ["问题 1", "问题 2"],
  "feedback": "给执行者的具体改进建议",
  "evidence": "你审查的具体依据（如：检查了第 X 行的数据，发现...）"
}
"""
```

### 3.3 返工循环控制

```python
# backend/app/services/ai_service.py
async def run_with_supervision(task, max_rounds=3, pass_threshold=80):
    """双 Agent 协作：执行 + 监督 + 返工"""
    executor = ExecutorAgent()
    supervisor = SupervisorAgent()

    for round_num in range(1, max_rounds + 1):
        # 1. 执行者干活
        result = await executor.run(task, context=task.context)

        # 2. 监督者评审
        review = await supervisor.review(task, result)
        score = review["overall_score"]

        log.info(f"Round {round_num}: score={score}, passed={review['passed']}")

        # 3. 判断是否通过
        if review["passed"] and score >= pass_threshold:
            return {
                "status": "success",
                "result": result,
                "review": review,
                "rounds": round_num
            }

        # 4. 不通过，把反馈塞回任务上下文
        task.context = build_feedback_context(
            previous_result=result,
            issues=review["issues"],
            feedback=review["feedback"]
        )

    # 超过最大轮数，标记为失败
    return {
        "status": "failed",
        "result": result,
        "review": review,
        "rounds": max_rounds,
        "error": f"监督者审核 {max_rounds} 轮未通过"
    }
```

---

## 四、彩蛋 1：插话引导（Interrupt）

**问题场景**：AI 干到一半，你发现方向错了，但只能等它跑完？

**解法**：插话发送 + 排队发送

### 4.1 两种模式对比

| 模式 | 触发时机 | 效果 |
|---|---|---|
| 🎯 **插话发送** | 方向错了，立刻停 | 消息**立即上送**，AI 立即采纳 |
| ⏳ **排队发送** | 想到补充信息 | 消息进队，**沙漏动画**提示，任务完成后自动发 |

### 4.2 核心实现

```python
# backend/app/services/ai_service.py
class InterruptManager:
    def __init__(self):
        self.interrupt_queue = asyncio.Queue()
        self.normal_queue = asyncio.Queue()

    async def send_interrupt(self, message: str):
        """插话：立即打断当前任务"""
        await self.interrupt_queue.put({
            "type": "interrupt",
            "message": message,
            "timestamp": time.time()
        })
        # 通知当前任务循环
        self.interrupt_event.set()

    async def send_queued(self, message: str):
        """排队：等当前任务完成"""
        await self.normal_queue.put({
            "type": "queued",
            "message": message,
            "timestamp": time.time()
        })

    async def check_interrupt_in_loop(self):
        """工具调用循环中检查插话"""
        if self.interrupt_event.is_set():
            msg = await self.interrupt_queue.get()
            self.interrupt_event.clear()
            return msg
        return None
```

### 4.3 工具调用前检查

```python
async def tool_call_loop(self, task):
    """AI 工具调用循环"""
    while not task.done:
        # 关键：在每次工具调用前检查插话
        interrupt_msg = await self.interrupt_manager.check_interrupt_in_loop()
        if interrupt_msg:
            log.info(f"收到插话: {interrupt_msg['message']}")
            # 清空已生成的工具调用，让 AI 基于新上下文重新决策
            task.clear_pending_tool_calls()
            # 注入新指令
            task.inject_message(interrupt_msg["message"])
            return self.continue_with_new_context(task)

        # 正常工具调用
        tool_call = await self.next_tool_call(task)
        await self.execute_tool(tool_call)
```

> 💡 **关键设计**：插话在**工具调用前**也会检查，确保 AI 一定能收到。

---

## 五、彩蛋 2：AI 自主学习（save_skill）

**问题场景**：每次都要告诉新员工"金额字段要千分位"，能不能让 AI 也学会？

**解法**：AI 主动保存规则为"技能"

### 5.1 技能三层管理

```python
# backend/app/models/ai_skill.py
class AISkill(db.Model):
    __tablename__ = "ai_skills"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # 技能名
    content = Column(Text, nullable=False)        # 技能内容
    skill_type = Column(Enum("system", "user", "auto"),
                       default="user")             # 系统/用户/自动学习
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uk_name_user"),
    )
```

### 5.2 save_skill 工具定义

```python
# backend/app/services/ai_service.py
SAVE_SKILL_TOOL = {
    "name": "save_skill",
    "description": """当用户表达了值得复用的规则、经验、最佳实践时，
    调用此工具保存为技能。例：
    - 用户说"记住这个规则""下次也这样""保存为知识"
    - 你发现用户纠正了你某个行为，并希望未来遵守
    - 表达有价值的经验/注意事项""",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "技能名称（短而清晰）"
            },
            "content": {
                "type": "string",
                "description": "技能详细内容"
            },
            "skill_type": {
                "type": "string",
                "enum": ["system", "user", "auto"],
                "description": "技能类型：系统/用户/自动学习"
            }
        },
        "required": ["name", "content"]
    }
}

async def _tool_save_skill(self, args, user_id):
    """保存技能实现"""
    # 同名技能自动更新，不重复创建
    existing = AISkill.query.filter_by(
        name=args["name"], user_id=user_id
    ).first()

    if existing:
        existing.content = args["content"]
        existing.updated_at = datetime.utcnow()
        return {"status": "updated", "skill_id": existing.id}

    skill = AISkill(
        name=args["name"],
        content=args["content"],
        skill_type=args.get("skill_type", "user"),
        user_id=user_id
    )
    db.session.add(skill)
    db.session.commit()
    return {"status": "created", "skill_id": skill.id}
```

### 5.3 监督者复用技能

```python
SUPERVISOR_PROMPT_WITH_SKILLS = """
你是一个严格的 AI 监督者。

【用户已保存的技能】（必须严格遵守）
{user_skills}

【执行者提交的结果】
{executor_output}

【额外检查项】
- 执行者是否遵守了所有相关用户技能？
- 如有违反，在 issues 中明确指出："违反了技能 X：..."
"""
```

---

## 六、彩蛋 3：Headroom 上下文压缩

**问题场景**：几万行报错日志扔给 AI，token 直接爆表

**解法**：按内容类型智能压缩，省 60-95% token

### 6.1 压缩策略

```python
# backend/app/utils/headroom.py
class HeadroomCompressor:
    """智能识别内容类型，应用针对性压缩策略"""

    def compress(self, content: str, content_type: str = "auto") -> dict:
        if content_type == "auto":
            content_type = self._detect_type(content)

        compressors = {
            "json": self._compress_json,
            "log": self._compress_log,
            "code": self._compress_code,
            "text": self._compress_text,
        }

        compressed = compressors[content_type](content)
        return {
            "original": content,
            "compressed": compressed,
            "ratio": 1 - len(compressed) / len(content),
            "type": content_type,
            "saved_tokens": self._count_tokens(content) - self._count_tokens(compressed)
        }

    def _compress_json(self, content: str) -> str:
        """JSON：保留结构 + 截断重复值"""
        data = json.loads(content)
        return json.dumps(self._truncate_repeated_values(data), indent=2)

    def _compress_log(self, content: str) -> str:
        """日志：去重 + 保留 ERROR 级别"""
        lines = content.split("\n")
        # 保留 ERROR/WARN，去重 INFO
        kept = []
        seen_info = set()
        for line in lines:
            if "ERROR" in line or "WARN" in line:
                kept.append(line)
            elif "INFO" in line:
                # 相似 INFO 只保留 1 条
                key = self._extract_log_key(line)
                if key not in seen_info:
                    seen_info.add(key)
                    kept.append(line)
        return "\n".join(kept)

    def _compress_code(self, content: str) -> str:
        """代码：保留关键结构，去注释"""
        # 去除单行注释
        return "\n".join(
            line for line in content.split("\n")
            if not line.strip().startswith("#")
        )
```

### 6.2 按模型独立启用

```python
# 后台配置：每个模型独立开关
HEADROOM_CONFIG = {
    "gpt-4o": {"enabled": True, "max_compress_ratio": 0.95},
    "claude-3.5-sonnet": {"enabled": True, "max_compress_ratio": 0.9},
    "deepseek-chat": {"enabled": False, "max_compress_ratio": 0.0},
    "gpt-3.5-turbo": {"enabled": True, "max_compress_ratio": 0.7}
}
```

### 6.3 实时统计

```python
# 每次压缩后记录
{
  "model": "gpt-4o",
  "content_type": "log",
  "original_tokens": 12450,
  "compressed_tokens": 620,
  "saved_tokens": 11830,
  "compression_ratio": 0.95,
  "cost_saved_usd": 0.059
}
```

> 💡 **关键设计**：JSON 压、日志压、代码压、文本压；**关键指令不压**。

---

## 七、AI Logo 自适配

加新模型还要上传 Logo？duck 不必。

```python
# backend/app/utils/provider_logo.py
LOGO_BUILTIN = {
    "openai": "https://...",
    "anthropic": "https://...",
    "deepseek": "https://...",
    "moonshot": "https://...",
    "zhipu": "https://...",
    # 15+ 主流厂商内置
}

async def get_provider_logo(provider_name: str) -> str:
    """Logo 自适配：内置 + 远程获取"""
    if provider_name in LOGO_BUILTIN:
        return LOGO_BUILTIN[provider_name]

    # 未匹配：通过 DuckDuckGo Favicon 远程获取
    domain = f"{provider_name}.com"
    favicon_url = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
    return favicon_url
```

**前端组件**：`<ProviderLogo :provider="model.provider" />` 自动渲染

---

## 八、完整工作流演示

**场景**：让 AI 帮你导出"上月华东区销售报表，并邮件给销售总监"

```python
# 1. 用户输入
task = {
    "type": "export_report",
    "params": {
        "region": "east",
        "period": "2025-08",
        "template": "monthly_sales",
        "send_to": "sales_director@company.com"
    }
}

# 2. 执行者 Agent 开始工作
executor.add_task(task)

# 3. 监督者介入
result = await run_with_supervision(
    task=task,
    max_rounds=3,
    pass_threshold=80
)

# 4. 输出
# {
#   "status": "success",
#   "result": {
#     "file": "华东区销售月度报表_202508.xlsx",
#     "email_sent": true,
#     "data_rows": 1245
#   },
#   "review": {
#     "overall_score": 92,
#     "passed": true
#   },
#   "rounds": 1
# }
```

**半路发现"加个对比上月"？**
→ 发送「插话消息」→ AI 立刻调头 → 再走一遍流程

---

## 九、为什么这是 AI Agent 该有的样子？

市面上大多数 AI 工具还在"单兵作战"。我们认为 **AI 的核心竞争力不在模型大小，而在协作机制**：

- 🤖 **AI 之间能协作**（执行者 + 监督者）
- 👤 **AI 和人能协作**（插话 + 排队 + 引导）
- 🧠 **AI 能积累经验**（自主学习 + 技能沉淀）
- 💰 **AI 跑得起**（Headroom 压缩）
- 🛡️ **AI 值得托付**（工单 + 监督 + 自动执行 + 签字）

---

## 十、部署实战

### Docker Compose 一键启动

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=mysql://user:pass@db:3306/excel_query
    depends_on:
      - db

  frontend:
    build: ./frontend
    ports:
      - "8080:8080"
    depends_on:
      - backend

  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

```bash
# 一键启动
git clone https://github.com/yourname/excel-database-query.git
cd excel-database-query
docker-compose up -d

# 访问
open http://localhost:8080
# 默认账号 admin / admin123
```

### 启用 AI 模块

1. 进入「系统配置」→「AI 配置」
2. 添加 OpenAI 兼容 API（支持 DeepSeek、月之暗面、智谱、ChatGLM 等）
3. 进入「Agent 管理」，配置执行者 + 监督者
4. 试用：在「AI 对话」中输入任务，观察双 Agent 协作过程

---

## 十一、核心特性速览

| 特性 | 说明 |
|---|---|
| 🤖 双 Agent 协作 | 执行者 + 监督者，自动返工 |
| 🎤 插话引导 | AI 干到一半能"插嘴" |
| 🧬 自主学习 | AI 自己记笔记，提炼技能 |
| 🗜️ Headroom 压缩 | Token 砍 60-95% |
| 🖼️ Logo 自适配 | 15+ 厂商免配置 |
| 🎨 5 套主题 | 默认蓝/粉色甜美/阳光橙/暗黑/豆绿 |
| 🔐 RBAC 三级权限 | 菜单/按钮/数据 |
| 🚇 SSH 隧道 | 内网数据库安全访问 |
| 🧩 流程编排 | 拖拽式 + 失败即停 + 三重防重 |
| 📡 SSE 实时推送 | 任务进度实时刷新 |

---

## 十二、结语

**项目地址**：[excel-database-query](https://github.com/yourname/excel-database-query)

如果这个项目对你有帮助：

- ⭐ **Star** 一下，给项目持续迭代的动力
- 🔀 **Fork** 走，按你的场景定制
- 💬 **评论区**告诉我你的 AI 协作场景
- 🐛 **Issues** 反馈 bug / 提需求

下一篇实战文章：《Headroom 上下文压缩算法详解：如何砍掉 95% token 不影响效果》

---

**本文作者**：[你的名字]
**联系方式**：[你的邮箱/微信]
**开源协议**：MIT（可商用）
**最后更新**：2026-09

---

## 📌 CSDN 发布元信息

**话题标签（推荐 8-10 个）**：
```
#AI Agent  #多智能体  #大模型应用  #LLM实战
#Python  #Flask  #Vue3  #开源项目  #Prompt工程
#监督学习  #开源  #ChatGPT  #深度学习
```

**摘要（SEO 优化）**：
```
本文介绍一个开源的 AI Agent 协作系统，采用执行者 + 监督者双 Agent 架构，
支持插话引导、AI 自主学习、Headroom 上下文压缩等高级特性。
完整代码 + Docker Compose 一键部署，适合中高级 AI 应用开发者学习参考。
```

**封面图推荐**：`docs/images/zhihu2-cover-dual-agent.png`
**字数**：约 4500 字（适合 CSDN 长文阅读习惯）
**原创声明**：✅ 勾选"原创"
**代码块**：✅ 12 段代码（CSDN 偏好带代码的技术文）

**SEO 关键词埋点**（自然融入正文）：
- "AI Agent 协作" — 主关键词
- "执行者 Agent" "监督者 Agent" — 长尾词
- "插话引导" "自主学习" — 特色词
- "Headroom 压缩" — 创新词
- "Flask + Vue3" "Docker Compose" — 技术栈词
