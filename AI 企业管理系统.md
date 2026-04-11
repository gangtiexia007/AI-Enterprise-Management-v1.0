# AI 企业管理系统 — 完整架构文档

> 版本：V4.0 | 日期：2026-04-09
> 状态：**V13.0.0 已部署 · Agent 集群体系重构中**
> 核心理念：千方百计AI = 自动化管理 AI OS，Agent Harness 驱动一切

---

## 目录

- [一、系统定位](#一系统定位)
- [二、核心设计理念](#二核心设计理念)
- [三、系统架构总览](#三系统架构总览)
- [四、Agent 运行时引擎](#四agent-运行时引擎)
- [五、Skill 系统与工具链](#五skill-系统与工具链)
- [六、业务引擎层](#六业务引擎层)
- [七、基础设施层](#七基础设施层)
- [八、Dashboard 页面体系](#八dashboard-页面体系)
- [九、数据库完整表结构](#九数据库完整表结构)
- [十、SmartForge 智铸引擎（规划中）](#十smartforge-智铸引擎规划中)
- [十一、技术栈与部署](#十一技术栈与部署)
- [十二、待完成事项](#十二待完成事项)

---

## 一、系统定位

### 1.1 一句话定义

**企业 AI 治理系统。** 用 AI Agent 替代企业中所有"管理者应该做但没时间做"的事——目标拆解、任务分配、执行追踪、绩效评估、辅导改进、知识沉淀、战略辅助。

让老板专注战略，让员工专注执行，中间所有管理动作由 AI 完成。

### 1.2 手机理论

千方百计AI 的底层哲学是**手机理论**：


| 层级  | 类比            | 千方百计AI                                               |
| --- | ------------- | ---------------------------------------------------- |
| 硬件  | 手机芯片          | LLM 大模型                                              |
| OS  | iOS / Android | Agent Loop + Memory + Approval + Channel + Skill SDK |
| APP | 微信 / 淘宝       | Agent 团队（每个部门/公司的 Agent 配置）                          |


- **OS 层不变**：Agent Loop 9 状态机、Memory L1-L5、Approval Gateway、Channel Router、Skill SDK、任务引擎、KPI 引擎、安全层、Dashboard 框架。
- **APP 层可变**：System Prompt、Skills 组合、数据表结构、KPI 定义、工作流配置、知识库内容、报表模板。

### 1.3 不做什么

- 不做 ERP / CRM / 财务 / 考勤 / OA 审批流（已有成熟工具）
- 不替代专业人事、法务、会计（AI 做的是管理辅助，不是专业执行）
- 不做"直接操作员工"的自动化（AI 只建议/提交审批，关键动作需人确认）

### 1.4 三级用户体系


| 层级  | 身份  | 访问范围                       |
| --- | --- | -------------------------- |
| T1  | 老板  | 全局数据 + 所有页面 + 设置向导         |
| T2  | 管理者 | 部门范围内数据 + Dashboard 业务页面   |
| T3  | 员工  | 仅 `/my` 员工自助工作台（任务、KPI、申诉） |


### 1.5 自动化四级


| 级别  | 行为        | 适用场景             |
| --- | --------- | ---------------- |
| L1  | 仅通知       | 新团队上线、低信心操作      |
| L2  | 建议 + 等审批  | 默认级别，AI 提出建议等老板批 |
| L3  | 自动执行 + 汇报 | 高信心的重复操作         |
| L4  | 全自动       | 成熟团队的日常流程        |


---

## 二、核心设计理念

### 2.1 Agent Harness 思想

本系统的核心不是"一个更聪明的模型"，而是一个 **Agent Harness（代理运行框架）**。

```
千方百计AI = Agent Harness + LLM
           = 状态机 + 上下文管理 + 工具系统 + 权限控制 + 失败恢复 + 协作分工
```

模型只是大脑的一部分，Harness 才是让大脑能持续干活的操作系统。

Harness 的核心职责：

1. **接收任务** — 把用户目标转换成 Agent 可执行的工作上下文
2. **编排工具** — 决定调用哪些 Skill（读数据、写任务、发消息）
3. **管理上下文** — 7 维度上下文加载 + 80% 阈值压缩
4. **控制权限** — P0-P4 五级权限 + 审批网关拦截
5. **处理失败** — 最多 15 轮重试 + 错误状态机恢复
6. **支持协作** — Director → Analyst / Coach / Executor 子 Agent 分工

### 2.2 架构硬规则（V3.6）


| 规则                     | 描述                               |
| ---------------------- | -------------------------------- |
| 数据只通过 Skill `@tool` 访问 | Engine 层禁止直连 DB，必须通过 DataGateway |
| Engine 层只做编排           | 接收数据 → 调用计算 → 返回结果，不包含 SQL       |
| APP 配置是声明式的            | JSON / DB 配置驱动，不在代码里硬编码业务逻辑      |
| 写操作走审批网关               | 敏感表的 insert/update/delete 自动提交审批 |


---

## 三、系统架构总览

### 3.1 六层架构

```
┌─────────────────────────────────────────────────┐
│                 Channel Layer                    │  飞书 / 企微 / Dashboard
│            (feishu.py, wecom.py, ws.py)          │
├─────────────────────────────────────────────────┤
│              Agent Runtime Layer                 │  AgentLoop 9 状态机
│     (agent_loop.py, sub_agent.py, context.py)    │  SubAgentRunner 四角色
│     (llm.py, model_router.py, prompt_engine.py)  │  ModelRouter + LLMClient
├─────────────────────────────────────────────────┤
│               Skill Layer                        │  @tool SDK + Registry
│       (sdk.py, registry.py, mcp_client.py)       │  builtin + custom + MCP
│       (builtin/: sqlite_data, knowledge,         │
│        file_parser, calc_engine, notification,   │
│        feishu_im, wecom_im, feishu_bitable)      │
├─────────────────────────────────────────────────┤
│              Engine Layer                         │  业务引擎（10 个）
│    (task, kpi, hiring, escalation, anomaly,      │  全部继承 EngineBase
│     cross_team, goal, customer, calc, decision)  │  通过 DataGateway 访问数据
├─────────────────────────────────────────────────┤
│            Infrastructure Layer                   │  记忆 / 权限 / 事件 / 审计
│     (memory.py, permission.py, eventbus.py,      │  EventBus + Hook + Audit
│      hooks.py, audit.py)                         │
├─────────────────────────────────────────────────┤
│              Safety Layer                         │  审批 / 影子 / 申诉
│    (approval.py, shadow.py, dispute.py)          │  ApprovalGateway + Shadow
├─────────────────────────────────────────────────┤
│              Data Layer                           │  SQLite WAL + DataGateway
│    (database.py, data_gateway.py, data_scope.py) │  DataScope 行级过滤
│    (migrations/001-006)                          │  6 份版本化迁移
└─────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
qfbj-co-server/
├── app/
│   ├── main.py                    # FastAPI 入口，lifespan 初始化
│   ├── channels/                  # 消息通道（飞书、企微、路由、通知）
│   ├── core/                      # 基础设施（config, database, models, enums, events,
│   │                              #   exceptions, security, data_gateway, data_scope, uploads）
│   ├── dashboard/                 # Web 管理面板
│   │   ├── app.py                 # Jinja2 + 导航 + render()
│   │   ├── auth.py                # 登录认证
│   │   ├── wizard.py              # 7 步设置向导
│   │   ├── ws.py                  # WebSocket 通信
│   │   ├── api/                   # 35 个路由模块
│   │   └── templates/             # base.html + 43 页面 + 7 步向导
│   ├── dream/                     # 做梦引擎（定时报告 + 知识蒸馏）
│   ├── engines/                   # 10 个业务引擎
│   ├── infra/                     # 基础设施（事件总线、Hook、审计、记忆、权限）
│   ├── runtime/                   # Agent 运行时（核心）
│   └── skills/                    # Skill SDK + Registry + 8 个内置 Skill
│       └── builtin/
├── data/migrations/               # 6 份 SQL 迁移
├── scripts/                       # 部署脚本
├── Dockerfile + docker-compose.yml
└── requirements.txt
```

---

## 四、Agent 运行时引擎

### 4.1 AgentLoop — 9 状态机

AgentLoop 是系统的核心引擎，驱动每一次 AI 员工交互。

```
IDLE → RECEIVING_INPUT → (是命令?) ─yes─→ COMMAND_ROUTING ─┐
                         └─no──→ LOADING_CONTEXT → THINKING  │
                                     ↑                      │
                                     │       ┌──────────────┘
                                     │       ↓
                         CALLING_TOOL ← (tool call?)
                              │
                              ↓
                         OBSERVING_RESULT → (更多轮次?) → THINKING
                                            └──no──→ RESPONDING → IDLE
                         ERROR_HANDLING → RESPONDING → IDLE
```

**关键约束：**

- 每次调用最多 **15 轮**（可按团队配置）
- 以 `/` 开头的消息绕过 LLM，直接路由到 Skill Registry
- 每个员工串行处理（`asyncio.Lock` 保证）
- `{current_plan_summary}` 在每次工具调用后更新

**核心数据结构 — `LoopSession`：**

```python
@dataclass
class LoopSession:
    team_id: str
    employee_id: str
    conversation_id: str
    state: AgentLoopState = IDLE
    turn: int = 0
    max_turns: int = 15
    messages: list[dict]        # LLM 对话历史
    tool_schemas: list[dict]    # 当前可用工具列表
    current_plan_summary: str   # 任务计划摘要
    model: str                  # 当前使用的模型
    tool_context: ToolContext   # 注入到每个工具调用的上下文
```

### 4.2 ContextManager — 7 维度上下文

每次 Agent 思考前，ContextManager 加载 7 个维度的上下文：


| 维度          | 来源                | 内容                       |
| ----------- | ----------------- | ------------------------ |
| identity    | `teams` 表         | Agent 身份 + System Prompt |
| employee    | `employees` 表     | 对话人的信息                   |
| history     | `conversations` 表 | 最近对话记录（超 20 轮自动摘要）       |
| memories    | `memories` 表      | L1-L5 多层记忆（按场景加载）        |
| knowledge   | `knowledge` 表     | 企业/部门知识条目                |
| team_status | 多表聚合              | 任务、审批、人数等运营计数            |
| goals       | `goals` 表         | 活跃目标及进度                  |


`**ContextPayload` 结构：**

```python
@dataclass
class ContextPayload:
    system_prompt: str = ""
    messages: list[dict]
    identity: dict
    employee: dict | None
    memories: list[dict]
    knowledge: list[dict]
    team_status: dict
    goals: list[dict]
```

**上下文压缩：** 当 token 数超过模型上下文窗口的 80% 时触发压缩，保留最近 5 轮完整对话，其余生成摘要。

### 4.3 SubAgentRunner — 四角色协作

Sub-Agent 系统实现了 Director → 子 Agent 的单层委派模式。

**四个标准角色：**


| 角色       | 权限上限    | 职责                      |
| -------- | ------- | ----------------------- |
| Director | P4      | 主 Agent，驱动对话，可调度子 Agent |
| Analyst  | P0 (只读) | 数据分析，生成洞察               |
| Coach    | P0 (只读) | 辅导建议，不执行任何操作            |
| Executor | P2 (可写) | 执行动作，P3+ 需审批            |


**权限钳制机制：**

```
effective_permission = min(parent_permission, role_cap, db_config_cap)
```

子 Agent 的实际权限永远不超过 Director 的权限，且受角色上限和数据库配置的三重约束。

**关键约束：**

- 每个子 Agent 获得独立的 `AgentLoop` 实例
- 仅 Director 可调用子 Agent（禁止链式递归）
- 子 Agent 仅加载其配置中指定的 Skill，不继承主 Agent 全部工具

`**SubAgentSpec` 结构：**

```python
@dataclass
class SubAgentSpec:
    name: str
    role: str               # director / analyst / coach / executor
    system_prompt: str
    model: str
    max_permission: int     # 钳制后的有效权限
    skills: list[str]       # 该子 Agent 可用的 Skill 列表
```

### 4.4 ModelRouter — 模型路由

`ModelRouter` 根据团队配置选择 LLM 模型：

- 优先使用 `primary_model`，失败时回退到 `fallback_model`
- 子 Agent 可通过 `model_override` 指定专用模型
- 通过 LiteLLM 统一调用各模型供应商（OpenAI、Anthropic、国产大模型等）
- `model_usage` 表记录每日 token 消耗

---

## 五、Skill 系统与工具链

### 5.1 Skill SDK — `@tool` 装饰器

所有暴露给 Agent 的函数**必须**用 `@tool` 装饰。装饰器自动完成：

- 权限检查（P0-P4）
- 审计日志记录
- 工具名注册（命名规范：`{skill_name}__{function_name}`）

**核心合约：**

```python
@dataclass
class ToolContext:
    team_id: str = ""
    employee_id: str = ""
    user_tier: str = "T3"
    caller_permission: int = 0
    actor: str = ""
    department: str = ""
    conversation_id: str = ""

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict
    call_id: str

@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    success: bool
    data: Any = None
    error: str = ""
    elapsed_ms: float = 0.0
```

### 5.2 SkillRegistry — 三源合一

SkillRegistry 是所有 Skill 的统一注册中心，合并三类来源：


| 来源          | 说明                | 注册方式                  |
| ----------- | ----------------- | --------------------- |
| **builtin** | Python `@tool` 函数 | 启动时自动扫描注册             |
| **custom**  | `SKILL.md` 文件     | 通过 `skill_md.py` 解析注册 |
| **MCP**     | 外部 MCP Server     | `mcp_client.py` 动态代理  |


**全局 Skill vs 团队 Skill：**

- `is_global=True` 的 Skill 对所有团队可用
- 团队通过 `team_skills` 表分配专属 Skill
- 子 Agent 通过 `sub_agents.skills_json` 限定可用工具

### 5.3 内置 Skill 清单


| Skill 模块         | 工具列表                                                     | 用途           |
| ---------------- | -------------------------------------------------------- | ------------ |
| `sqlite_data`    | query, insert, update, delete, count                     | 数据库 CRUD     |
| `knowledge`      | search, upload, list                                     | 知识库检索与管理     |
| `file_parser`    | parse_excel, parse_markdown, parse_text, parse_csv       | 文件解析         |
| `calc_engine`    | evaluate, batch_evaluate                                 | 公式计算（KPI、薪酬） |
| `notification`   | send, send_card, merge_and_send                          | 通知推送         |
| `feishu_im`      | send_message, send_card, upload_file                     | 飞书消息         |
| `wecom_im`       | send_message, send_card                                  | 企微消息         |
| `feishu_bitable` | create_table, append_records, query_records, list_tables | 飞书多维表格       |


**特殊运行时工具：**

- `invoke_sub_agent` — 非 `@tool` 装饰，在 AgentLoop 中动态注入，当团队配置了子 Agent 时可用
- `mcp_`* 前缀工具 — 自动路由到对应 MCP Server

---

## 六、业务引擎层

### 6.1 EngineBase — 统一基类

所有业务引擎继承 `EngineBase`，通过 `DataGateway` 访问数据，**禁止直连 DB**。

```python
class EngineBase:
    def __init__(self, gateway: DataGateway, ctx: GatewayContext):
        self.gateway = gateway
        self.ctx = ctx

    # 读操作
    def _query(table, conditions, order_by, limit, offset)
    def _get_by_id(table, record_id)
    def _count(table, conditions)
    def _execute(sql, params)

    # 写操作（自动审计）
    def _insert(table, data)
    def _update(table, record_id, data)
    def _delete(table, record_id)
```

### 6.2 十大业务引擎


| 引擎               | 文件              | 职责                        |
| ---------------- | --------------- | ------------------------- |
| TaskEngine       | `task.py`       | 任务分配 → 催办 → 反馈 → 评分 → 完成  |
| KPIEngine        | `kpi.py`        | KPI 定义、自动评分、系统指标采集        |
| HiringEngine     | `hiring.py`     | 画像生成 → 面试题 → 候选人评分 → 入职计划 |
| EscalationEngine | `escalation.py` | 逾期检测 → 渐进催办 → 升级上报        |
| AnomalyEngine    | `anomaly.py`    | 异常检测（逾期堆积、绩效波动、离职风险）      |
| CrossTeamEngine  | `cross_team.py` | 跨团队任务依赖追踪与触发              |
| GoalEngine       | `goal.py`       | OKR 目标层级分解 + 进度追踪         |
| CustomerEngine   | `customer.py`   | 客户生命周期管理（健康度、跟进、反馈）       |
| CalcEngine       | `calc.py`       | 通用公式计算引擎（simpleeval）      |
| DecisionEngine   | `decision.py`   | AI 决策记录 → 人工复核 → 准确率追踪    |


### 6.3 DataGateway — 安全数据网关

`DataGateway` 是引擎层和 Skill 层的统一数据访问入口：

```python
@dataclass
class GatewayContext:
    team_id: str = ""
    user_tier: str = "T1"
    employee_id: str = ""
    department: str = ""
    actor: str = "system"
```

**安全机制：**

1. **DataScope 行级过滤** — T2 用户只能查看本部门数据，T3 只能查看本人数据
2. **表级访问控制** — `WRITABLE_TABLES` 白名单限制可写表
3. **审计日志** — 每次写操作自动记录到 `audit_logs`
4. **审批网关集成** — 敏感表的写操作自动提交审批

---

## 七、基础设施层

### 7.1 记忆系统（L1-L5）

5 层记忆，按场景动态加载：


| 层级  | 内容            | 特点        |
| --- | ------------- | --------- |
| L1  | 系统硬规则         | 不可覆盖，全局生效 |
| L2  | 团队 SOP / 运营规则 | 按部门配置     |
| L3  | 员工画像 / 行动卡片   | 个人级别      |
| L4  | 业务知识 / 案例库    | 可检索       |
| L5  | 对话摘要 / 对话记忆   | 自动生成      |


**9 大场景的记忆调度：**


| 场景     | 加载层级                   |
| ------ | ---------------------- |
| 日常聊天   | L1 + L2 + L3 + L5      |
| KPI 评分 | L1 + L2 + L3 + L4      |
| 任务催办   | L1 + L2 + L3           |
| 员工辅导   | L1 + L2 + L3 + L4 + L5 |
| 报告生成   | L1 + L2 + L4           |
| 风险预警   | L1 + L2 + L3 + L4      |
| 客户咨询   | L1 + L2 + L3 + L4 + L5 |
| 审批处理   | L1 + L2 + L3 + L4      |
| 申诉处理   | L1 + L2 + L3 + L4      |


### 7.2 事件总线 (EventBus)

系统内部的异步事件发布/订阅机制，用于解耦模块间通信：

- `webhook.data_received` — 外部数据推送
- `approval.`* — 审批状态变更
- `task.*` — 任务状态变更
- Hook 规则订阅事件并触发动作

### 7.3 Hook 规则系统

支持 4 种 Hook 动作类型：

- `send_notification` — 发送通知
- `create_approval` — 提交审批
- `create_task` — 创建任务
- `update_status` — 更新记录状态

### 7.4 审批网关（ApprovalGateway）

4 级自动化 + 信心值降级：

```
提交操作 → ApprovalGateway.submit()
         → 检查自动化等级 (L1-L4)
         → 检查信心值 (A/B/C)
         → 影子模式拦截 (shadow/live)
         → A+L3/L4 = 自动执行
         → B+L2 = 等待审批
         → C = 降级到 L1 (仅通知)
```

### 7.5 影子模式（Shadow Mode）

新团队上线前的试运行机制：

- 所有 AI 动作只写入 `shadow_results`，不产生真实副作用
- 影子期结束后对比 AI 决策 vs 人工决策，生成准确率报告
- 达到信心基线后才切换到 live 模式

### 7.6 做梦引擎（Dream Engine）

基于 APScheduler 的定时任务系统：


| 任务        | 时间           | 功能                 |
| --------- | ------------ | ------------------ |
| DB 备份     | 01:00        | SQLite 热备份，7 天滚动保留 |
| 记忆蒸馏      | 02:00        | L5 对话记忆 → L4 知识提炼  |
| 知识提取      | 03:00        | 从对话/文档中提取知识条目      |
| 日报生成      | 06:00        | 各团队日报              |
| 周报生成      | 周日 06:00     | 各团队周报              |
| 月报生成      | 每月 1 日 06:00 | 各团队月报              |
| 逾期检测 + 催办 | 每 30 分钟      | 任务超期自动催办 + 渐进上报    |
| 审批过期      | 每 30 分钟      | 超时审批自动处理           |
| KPI 自动评分  | 23:00        | 系统指标自动打分           |
| 异常检测      | 09:00        | 全面扫描异常             |
| 留存预警      | 09:00        | 离职风险预警             |


---

## 八、Dashboard 页面体系

### 8.1 技术方案

- **后端**：FastAPI + Jinja2 模板渲染
- **前端**：TailwindCSS + Alpine.js + HTMX + ECharts
- **认证**：bcrypt 密码哈希 + session cookie
- **聊天**：底部展开式全局聊天栏（HTTP POST `/api/chat`）

### 8.2 导航结构


| 分组             | 页面       | 路径               |
| -------------- | -------- | ---------------- |
| **总览**         | 总览       | `/`              |
| **Agent**      | Agent 管理 | `/agents`        |
|                | 定时任务     | `/schedules`     |
| **团队**         | 部门管理     | `/teams`         |
|                | 员工管理     | `/employees`     |
|                | 招聘管理     | `/hiring`        |
|                | 客户管理     | `/customers`     |
| **任务与审批**      | 审批中心     | `/approvals`     |
|                | 任务管理     | `/tasks`         |
|                | 升级处理     | `/escalations`   |
|                | 申诉中心     | `/disputes`      |
| **规则与知识**      | KPI 管理   | `/kpi`           |
|                | 目标管理     | `/goals`         |
|                | 薪酬计算     | `/salary`        |
|                | 知识库      | `/knowledge`     |
|                | 记忆管理     | `/memory`        |
|                | 快捷指令     | `/commands`      |
|                | 跨团队依赖    | `/cross-team`    |
| **系统**         | 模型管理     | `/models`        |
|                | LLM 路由配置 | `/llm-config`    |
|                | 决策日志     | `/decisions`     |
|                | Hook 规则  | `/hooks`         |
|                | 影子报告     | `/shadow-report` |
|                | 审计日志     | `/audit-logs`    |
|                | 做梦报告     | `/dream-reports` |
|                | 数据源管理    | `/data-sources`  |
|                | 数据质量     | `/data-quality`  |
|                | 对话记录     | `/conversations` |
| **知识与技能**      | 智能配置     | `/smart-config`  |
| **员工工作台** (T3) | 首页       | `/my`            |
|                | 我的任务     | `/my/tasks`      |
|                | 我的 KPI   | `/my/kpi`        |


共计 **43 个页面模板 + 7 步设置向导**。

### 8.3 设置向导（7 步）


| 步骤     | 内容                 |
| ------ | ------------------ |
| Step 1 | 企业基本信息             |
| Step 2 | LLM 模型配置（含连接测试）    |
| Step 3 | 管理员账号              |
| Step 4 | 创建第一个部门            |
| Step 5 | 添加团队成员             |
| Step 6 | 消息通道（飞书/企微）        |
| Step 7 | 完成 → 引导创建第一个 Agent |


### 8.4 Agent 管理页面

Agent 管理页面支持 Agent 集群的层级管理：

- **集群列表视图**：显示顶层 Agent（Director/Boss/General）及其子 Agent
- **团队模板快速创建**：一键创建预配置的 Agent 集群（如"销售团队模板" = Director + Analyst + Coach + Executor）
- **Agent 编辑表单**：配置 System Prompt、模型、权限等级、Skills 分配
- **子 Agent 管理**：在 Director 下添加/编辑子 Agent，配置角色和 Skills

### 8.5 API 端点（关键）


| 方法   | 路径                        | 功能           |
| ---- | ------------------------- | ------------ |
| GET  | `/health`                 | 健康检查         |
| POST | `/webhook/feishu`         | 飞书回调         |
| POST | `/api/chat`               | HTTP 聊天接口    |
| POST | `/api/llm-test`           | LLM 连接测试     |
| POST | `/api/data-quality/check` | 数据质量检查       |
| POST | `/api/webhook/data`       | 外部数据推送       |
| POST | `/api/upload/parse`       | 文件上传解析       |
| WS   | `/ws/chat`                | WebSocket 聊天 |


---

## 九、数据库完整表结构

SQLite + WAL 模式，6 份版本化迁移，共 **46 张表**。

### 9.1 核心表（001_initial.sql — 34 张）


| 表名                    | 说明             | 关键字段                                                                     |
| --------------------- | -------------- | ------------------------------------------------------------------------ |
| `schema_version`      | 迁移版本追踪         | version, applied_at                                                      |
| `teams`               | 部门/团队          | tier(T1/T2/T3), status, system_prompt, primary_model, automation_profile |
| `team_bots`           | 团队消息通道         | channel(feishu/wecom), app_id_encrypted                                  |
| `employees`           | 员工             | role(boss/manager/employee), feishu_id, wecom_id                         |
| `sub_agents`          | 子 Agent（运行时使用） | role(director/analyst/coach/executor), skills_json, max_permission       |
| `models`              | LLM 模型配置       | provider, api_key_encrypted, cost_tier, token limits                     |
| `model_usage`         | 模型用量统计         | prompt_tokens, completion_tokens, total_tokens                           |
| `skills`              | Skill 注册表      | source(builtin/custom/mcp), tools_json, is_global                        |
| `team_skills`         | 团队 Skill 分配    | team_id, skill_id, assigned_to                                           |
| `kpi_definitions`     | KPI 定义         | metrics_json, scoring_json, weight, source_type                          |
| `kpi_scores`          | KPI 评分记录       | scores_json, total_score, grade, status                                  |
| `goals`               | 目标管理           | level(company/department/personal), parent_id, progress                  |
| `tasks`               | 任务             | status(7 种状态), score, deadline_at                                        |
| `task_feedbacks`      | 任务反馈           | content, file_path, feedback_type                                        |
| `escalations`         | 催办记录           | level(employee/manager/boss), response_at                                |
| `memories`            | 记忆             | layer(L1-L5), reference_count, is_verified                               |
| `knowledge`           | 知识库            | scope(company/department), source(manual/dream), status                  |
| `decision_logs`       | 决策日志           | decision, expected_result, actual_result, review_status                  |
| `audit_logs`          | 审计日志           | actor, action, resource_type, details_json                               |
| `conversations`       | 对话记录           | turns_json, summary, channel                                             |
| `dream_reports`       | 做梦报告           | report_type(daily/weekly/monthly), stats_json                            |
| `dashboard_users`     | 管理面板用户         | tier(T1/T2/T3), password_hash                                            |
| `hiring_profiles`     | 招聘画像           | profile_json                                                             |
| `interview_templates` | 面试模板           | required_questions, scoring_criteria_json                                |
| `candidates`          | 候选人            | interview_scores_json, overall_score, status                             |
| `onboarding_plans`    | 入职计划           | plan_json, progress                                                      |
| `customers`           | 客户             | profile_json, assigned_employee_id, scope                                |
| `customer_contacts`   | 客户跟进记录         | content, contact_type                                                    |
| `customer_feedbacks`  | 客户反馈           | feedback_type, content, status                                           |
| `task_dependencies`   | 跨团队任务依赖        | upstream_task_id, downstream_task_id                                     |
| `reward_rules`        | 薪酬规则           | kpi_grade, formula                                                       |
| `reward_calculations` | 薪酬计算结果         | calculated_amount, formula_used, variables_json                          |
| `approval_requests`   | 审批请求           | type, automation_level, confidence, status                               |
| `shadow_results`      | 影子结果           | original_action_json, shadow_data_json                                   |
| `team_shadow_config`  | 影子模式配置         | mode(shadow/live), shadow_duration_days                                  |
| `disputes`            | 申诉             | type, evidence_json, resolution, status                                  |


### 9.2 扩展表（002-006）


| 迁移  | 表名                      | 说明                                 |
| --- | ----------------------- | ---------------------------------- |
| 002 | `commands`              | 快捷指令                               |
| 003 | `coaching_records`      | 辅导记录                               |
| 003 | `report_templates`      | 报表模板                               |
| 004 | `data_matches`          | 数据匹配（订单/线索等）                       |
| 004 | `bitable_configs`       | 飞书多维表格同步配置                         |
| 004 | `file_processing_queue` | 文件处理队列                             |
| 005 | `agents`                | 独立 Agent（与 team 解耦）                |
| 005 | `agent_assignments`     | Agent 分配（team/department/employee） |
| 005 | `scheduled_tasks`       | 定时任务配置                             |
| 006 | `agent_skills`          | Agent-Skill 多对多绑定                  |


**006 额外字段：** `agents` 表增加 `parent_agent_id`、`permission_level`、`writable`、`default_skills`。

---

## 十、SmartForge 智铸引擎（规划中）

### 10.1 定位

SmartForge 是千方百计AI OS 的核心扩展模块——面向老板的 AI 二次开发引擎。

```
传统二开：老板有需求 → 找开发者 → 写代码 → 测试 → 部署
SmartForge：老板有需求 → 在飞书/Dashboard 跟 AI 聊 → AI 生成 Skill → 沙箱验证 → 直接能用
```

### 10.2 与 Dify 的区别


| 维度  | Dify       | SmartForge                    |
| --- | ---------- | ----------------------------- |
| 定位  | LLM 应用开发平台 | 企业管理 AI OS 的业务锻造引擎            |
| 用户  | 开发者        | 老板（非技术人员）                     |
| 交互  | 画布拖拽       | 自然语言对话                        |
| 输出  | JSON 工作流   | Python Skill 文件（遵循 @tool SDK） |
| 安全  | 信任开发者      | 不信任生成代码，多层防护                  |


### 10.3 九大原语

SmartForge 将所有企业管理操作抽象为 9 个原语：


| 原语      | 代码                 | 对应能力                         |
| ------- | ------------------ | ---------------------------- |
| **查数据** | `DATA.query`       | `sqlite_data__query`         |
| **写数据** | `DATA.write`       | `sqlite_data__insert/update` |
| **算指标** | `CALC.eval`        | `calc_engine__evaluate`      |
| **发通知** | `NOTIFY.send`      | `notification__send`         |
| **建任务** | `TASK.create`      | DataGateway → tasks 表        |
| **要审批** | `APPROVE.submit`   | ApprovalGateway.submit()     |
| **存记忆** | `MEMORY.save`      | memories 表                   |
| **查知识** | `KNOWLEDGE.search` | BM25 + jieba                 |
| **调外部** | `EXTERNAL.call`    | MCP / HTTP                   |


### 10.4 安全四层防护

```
第一层：AST 白名单 — 只允许安全的 Python 子集
第二层：静态分析 — 检查导入、网络调用、文件操作
第三层：沙箱执行 — Docker 隔离运行，限时限资源
第四层：影子模式 — 新 Skill 强制走影子验证
```

### 10.5 实现路径

1. 阶段 A：需求理解与 Skill 生成（对话 → AST → Python 文件）
2. 阶段 B：沙箱验证与部署（安全检查 → 沙箱测试 → 注册到 SkillRegistry）
3. 阶段 C：版本管理与回滚（Skill 版本历史 → 一键回滚 → A/B 测试）

> **当前状态：需求设计阶段，尚未开始编码。**

---

## 十一、技术栈与部署

### 11.1 技术栈


| 类别        | 技术                                       |
| --------- | ---------------------------------------- |
| 语言        | Python 3.12+                             |
| Web 框架    | FastAPI + Uvicorn                        |
| 模板        | Jinja2                                   |
| 前端        | TailwindCSS + Alpine.js + HTMX + ECharts |
| 数据库       | SQLite (WAL) + aiosqlite                 |
| LLM 调用    | LiteLLM + OpenAI SDK                     |
| 定时任务      | APScheduler 3.x                          |
| 飞书集成      | lark-oapi                                |
| 企微集成      | wecom-aibot-python-sdk                   |
| 知识检索      | rank-bm25 + jieba                        |
| 公式计算      | simpleeval                               |
| 文件解析      | openpyxl + python-docx                   |
| HTTP 客户端  | httpx                                    |
| WebSocket | websockets                               |
| MCP 集成    | mcp SDK                                  |
| 加密        | cryptography + bcrypt                    |
| 容器化       | Docker + docker-compose                  |


### 11.2 部署

- **服务器**：159.75.48.163
- **部署方式**：rsync + SSH（paramiko），或 Docker
- **反向代理**：Nginx（`scripts/nginx.conf`）
- **启动命令**：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **备份**：SQLite 每日热备份到 `data/backups/`，7 天滚动

### 11.3 环境变量


| 变量                        | 说明                 |
| ------------------------- | ------------------ |
| `QFBJ_ENCRYPT_KEY`        | 对称加密密钥（API Key 加密） |
| `QFBJ_DB_PATH`            | 数据库文件路径            |
| `QFBJ_HOST` / `QFBJ_PORT` | 监听地址               |
| `QFBJ_DEBUG`              | 调试模式               |
| `QFBJ_MAX_AGENT_TURNS`    | 最大 Agent 轮次        |


---

## 十二、待完成事项

### 12.1 运行时对接（高优先级）


| 事项                              | 说明                                               |
| ------------------------------- | ------------------------------------------------ |
| AgentLoop 从 `agent_skills` 加载工具 | 当前仍从 `team_skills` 加载，需改造为从 `agent_skills` 表读取   |
| `sub_agents` 表与 `agents` 表统一    | 运行时使用 `sub_agents`，Dashboard 使用 `agents`，两套数据需合并 |
| 子 Agent 独立推理                    | 每个子 Agent 获得独立 AgentLoop 实例（已实现），但 Skill 加载路径需对齐 |


### 12.2 Skills 独立管理


| 事项            | 说明                               |
| ------------- | -------------------------------- |
| Skills 独立管理页面 | CRUD + 分配 + 使用统计的完整 Dashboard 页面 |
| Skills 分配模型决策 | 全局 Skill 是否自动授权，还是需要手动分配到 Agent  |
| Skill 调用统计    | 记录每个 Skill 的调用频次和成功率             |


### 12.3 Agent 集群增强


| 事项                | 说明                       |
| ----------------- | ------------------------ |
| Director 调度策略     | LLM 自主决策 vs 规则路由 vs 混合   |
| 子 Agent Prompt 模板 | 标准化各角色的 System Prompt 模板 |
| 自定义集群模板           | 允许用户自定义模板并保存复用           |


### 12.4 SmartForge 开发


| 事项   | 说明                |
| ---- | ----------------- |
| 阶段 A | 需求对话 → Skill 代码生成 |
| 阶段 B | AST 白名单 + 沙箱执行    |
| 阶段 C | 版本管理 + 回滚         |


---

> 文档基于 `qfbj-co-server` 实际代码重写，反映 V13.0.0 的真实实现状态。
> 最后更新：2026-04-09

