# 千方百计AI (QFBJ-AI) — OS 基座代码

Enterprise AI governance system for team management, KPI scoring, task dispatch, and reward calculation — with a full safety layer ensuring human-in-the-loop oversight.

> **注意**：此目录（qfbj/）是 OS 基座代码。三家公司的实例已独立 fork：
> - **千帆海**（跨境电商）→ `/Users/gangtiexia/文档/【千帆海】/qfh-server/`
> - **千万星河**（软件ERP销售）→ `/Users/gangtiexia/文档/【千万星河】/qwxh-server/`
> - **千方百计科技**（短视频IP）→ `/Users/gangtiexia/文档/【千方百计科技】/qfbj-co-server/`
>
> 各公司业务开发请在对应 fork 目录进行。OS 层 bug 修复后手动同步。

## 功能列表

| 模块 | 功能 | 说明 |
|------|------|------|
| Core | Team Registry (F02) | 团队 CRUD、自动化配置、机器人绑定 |
| Core | Employee Manager | 员工管理、角色分配、部门调动 |
| Core | Data Scope | 数据隔离、权限范围控制 |
| Core | Security | 加密、凭证管理、密码哈希 |
| Infra | EventBus (F29) | asyncio.Queue 事件发布/订阅，关键事件持久化 |
| Infra | Memory (F27) | 5 层记忆管理（L1-L5），9 场景 × 5 层调度表 |
| Infra | Permission (F28) | T1/T2/T3 层级 + P0-P4 操作级别校验 + FastAPI 中间件 |
| Infra | Audit (F31) | 异步批量审计日志（缓冲 + 定时 flush），1 年留存 |
| Infra | Hooks (F30) | 事件→条件(simpleeval)→动作管线，仪表盘可配置 |
| Skills | SDK (F12) | @tool 装饰器、ToolCall/ToolResult 合约、自动权限检查与审计 |
| Skills | Registry (F16) | 统一技能注册（builtin/custom/MCP），按 team_id 查询，MCP 工具 schema 自动合并 |
| Skills | SKILL.md Parser (F14) | 解析 SKILL.md 为 prompt-based 技能模板 |
| Skills | MCP Client (F15) | MCP 服务端工具发现与代理调用 |
| Skills | sqlite_data (F13) | **数据网关** — 运行时唯一数据路径，自动注入 DataScope |
| Skills | knowledge (F13) | BM25 + jieba 中文知识库搜索 |
| Skills | file_parser (F13) | Excel/CSV/Markdown/Text 文件解析 |
| Skills | calc_engine (F13) | simpleeval 沙箱公式求值（单条/批量） |
| Skills | notification (F13) | 抽象通知路由 + 智能合并 |
| Skills | feishu_im (F13) | 飞书消息/卡片/文件发送；`build_approval_card` 审批模板；异步 tenant token |
| Skills | feishu_bitable (F13) | 飞书多维表格（Bitable）：建表、批量追加记录、查询/分页、列出数据表；Open API + `tenant_access_token`（团队 Bot 或 `FEISHU_APP_*`） |
| Skills | wecom_im (F13) | 企业微信消息/卡片发送 |
| Channels | Router (F22) | 统一入站消息路由，bot_id→team_id 映射，`send_reply()` 出站回复路由 |
| Channels | Feishu (F23) | 飞书 webhook：Encrypt Key 签名校验（可选）、消息解析（open_id/chat_id/附件）、入站回复、审批卡片构建、`card.action.trigger` 批准/驳回并 PATCH 卡片、文件/图片消息下载与解析 |
| Channels | WeCom (F24) | 企业微信 WebSocket 长连接 + 自动重连 + 启动时自动连接已启用的团队 Bot + `send_message()` 出站回复 |
| Channels | Bot Manager (F25) | Bot 凭证加密存储、热重载、连接测试 |
| Channels | Notification (F26) | 事件驱动通知系统，智能合并 + 渠道路由 |
| Safety | Approval Gateway (F44) | 4 级自动化审批（L1-L4）+ 置信度降级 |
| Safety | Shadow Mode (F45) | 影子模式：干跑记录、准确率分析 |
| Safety | Dispute Center (F46) | 员工申诉：提交、举证、裁决、推翻 |
| Engines | Task Engine (F17) | 任务创建/分派/评分/完成，三维评分体系 |
| Engines | KPI Engine (F18) | KPI 定义/评分/改进建议，数据源映射 |
| Engines | Goal Engine (F19) | 目标分解/级联/进度追踪/树形结构 |
| Engines | Escalation Engine (F20) | 三级超时升级（员工→经理→老板），可配置间隔；`check_overdue_tasks()` 批量标记超期并落库升级 + 事件 |
| Engines | KPI 系统自动评分 | `source_type=system` 指标（日报提交率、Sprint/完成率）按周期 upsert `kpi_scores` |
| Engines | Anomaly Engine | 沉默反馈、严重超期任务 → `risk_alert` 审批单 + `approval.submitted` 事件 |
| Engines | Calc Engine (F21) | simpleeval 公式计算 + KPI 奖金联动 |
| Engines | Cross-Team (F43) | 跨团队任务依赖/阻塞检测/瓶颈分析 |
| Engines | Hiring (F40) | 招聘画像/JD 生成/面试模板/候选人评分/入职计划 |
| Engines | Decision Logger (F41) | 决策记录/指标追踪/前后对比/月度复盘 |
| Engines | Customer Memory (F42) | 客户管理/联系记录/反馈/流失预警 |
| Dream | Memory Distiller (F32) | 夜间 LLM 蒸馏对话为要点，写入 L5；7 日对话清理 |
| Dream | Knowledge Extractor (F33) | 高分任务/KPI、长文本任务反馈、`reviewed` 决策日志 → 知识候选 |
| Dream | Report Generator (F34) | 日/周/月报统计 + LLM 摘要写入 `dream_reports.summary` |
| Dream | Report Push | 报告生成后推送：飞书 webhook / `notify_open_id`、企微 webhook |
| Dream | Template Engine (F35) | 内置通知/报告模板渲染 |
| Dream | Dream Scheduler | APScheduler：蒸馏 02:00、知识提取 03:00、日报 06:00 / 周报周日 06:00 / 月报每月 1 日 06:00；超期与渐进升级（30min）；审批过期清理（30min）；KPI 23:00；异常与留存 09:00 |
| Runtime | Agent Loop (F06) | 9 状态机、15 轮限制、/命令路由、计划摘要更新、子Agent调用（invoke_sub_agent 内置工具）、上下文自动压缩、长对话摘要持久化、文件消息自动解析（Excel/CSV/TXT/MD/JSON） |
| Runtime | Context Loader (F07) | 7 维上下文加载、80% 阈值压缩、压缩验证、PromptEngine 系统提示词渲染、对话历史摘要注入 |
| Runtime | LLM Client (F08) | litellm 统一调用；`deepseek-chat` 等短名自动映射为 `deepseek/…`；支持按请求传入 DB 解密的 `api_key` |
| Runtime | Model Router (F09) | 模型选择（主/备/默认）、按日 token 追踪、80/90/95% 预算告警 |
| Runtime | Sub-Agent (F10) | 4 角色（Director/Analyst/Coach/Executor）、权限隔离 |
| Runtime | Prompt Engine (F11) | 系统提示词变量插值、缺失变量段落跳过 |
| Dashboard | Framework (F36) | FastAPI + Jinja2 + HTMX + Alpine.js + TailwindCSS 管理后台；全局 Toast（`?msg=` + `@toast.window`） |
| Dashboard | Auth (F36) | bcrypt + itsdangerous 签名 Cookie + T1/T2/T3 层级鉴权；T2 按 `employee_id→employees.team_id` 注入 `user_teams`，列表与写操作仅可见本团队数据；T3 仅可访问 `/my` 员工自助；`/wizard` 未登录可访问（首次引导） |
| Dashboard | 员工自助 /my | 工作台、我的任务（标记完成→`submitted`）、我的 KPI、提交申诉（`disputes`） |
| Dashboard | 辅导记录 | `coaching_records`：员工展开行内列表 + `POST /employees/{id}/coaching` |
| Dashboard | 日报模板 | `report_templates`：团队详情「日报模板」页签 + `POST /teams/{id}/report-template` |
| Dashboard | Setup Wizard (F36) | 3 步引导：公司信息 → 配置 LLM → 配置飞书机器人；完成后自动创建 Boss Agent（`is_boss_agent=1`，`data_scope='*'`）并绑定飞书机器人，302 跳转至总览或登录页（`?msg=` 成功提示）；模板 `wizard/step1`–`step3` |
| Dashboard | WebSocket (F38) | 登录 Cookie 校验；首包 `team_id` + `AgentLoop` 走真实 LLM；流式分块推送；智能面板（实体关键词触发关联数据）；T3 员工只读接入（限本团队） |
| Dashboard | P01 总览 | CEO 风格仪表盘：6 项 KPI 卡（团队/进行中/待审批/目标达成率/完成率/超期）+ 待审批 Top5（优先级/置信度/快速通过）+ 超期预警 + 团队绩效表 + 审计动态 + AI 对话与智能面板条 + 影子模式倒计时 |
| Dashboard | P02 团队列表 | 卡片网格、状态徽章、机器人状态、创建对话框 |
| Dashboard | P02b 员工管理 | 全库员工表、按团队/角色筛选、行内展开编辑、新建弹窗、删除（外键冲突时提示） |
| Dashboard | P03 团队详情 | 12 个标签页（含「日报模板」）+ 右侧操作栏 + 发布（`POST /teams/{id}/publish`）/删除 |
| Dashboard | P04 快捷指令 | 内置 4 个 (/日报/KPI/任务/申诉) + 自定义指令 CRUD（含删除） |
| Dashboard | P05 审批中心 | 双栏布局 + 置信度色标(A/B/C) + HTMX 右侧详情；待办多选批量批准/驳回；详情解析 `detail_json`、关联团队与员工（`detail_json.employee`）跳转 |
| Dashboard | P06 任务管理 | 筛选 + 表格 + HTMX 详情 + 详情页改状态/评分/反馈/删除 |
| Dashboard | P07 KPI 管理 | 按团队分组 + 趋势 ECharts 图表 + 数据源映射；详情页编辑/删除（`POST /kpi/{id}/update`、`POST /kpi/{id}/delete`） |
| Dashboard | KPI 评分记录 | `GET/POST /kpi/scores`：多条件筛选、联合 KPI/员工展示、弹窗录入或按人+指标+周期更新评分 |
| Dashboard | 薪酬计算 | `GET /salary`、`POST /salary/calculate`：按团队周期批量匹配奖惩规则并写入 `reward_calculations`，列表筛选与规则对照 |
| Dashboard | P08 升级处理 | 按紧急度排序 + 时间线视图 + 单条「标记已响应」（写入 `response_at`） |
| Dashboard | P09 申诉中心 | 双栏布局 + 证据链 + 维持/推翻操作 + 提交申诉弹窗 + 证据上传 |
| Dashboard | P10 知识库 | 分类树 + 范围筛选 + 文本/文件上传（`POST /knowledge/upload`，Excel/CSV 摘要）+ 列表编辑/删除；待审页通过/拒绝（`POST /knowledge/{id}/update|delete|approve|reject`） |
| Dashboard | P11 记忆管理 | L1-L5 层级标签 + 引用计数 + 审计元数据 |
| Dashboard | P12 模型管理 | 用量进度条 + API Key 测试 + 预算告警 + 编辑/删除/启停 |
| Dashboard | P13 客户管理 (F42) | 客户列表（筛选/统计）+ 详情页（联系记录/反馈时间线）+ 新增/删除/状态变更 |
| Dashboard | P14 招聘管理 (F40) | 招聘画像 + 候选人管理（状态流转：待处理→筛选→面试→评分→Offer→入职/拒绝）+ 统计卡片 |
| Dashboard | P15 决策日志 (F41) | 决策列表（按团队/状态筛选）+ 详情页（指标快照对比、复盘结果、评估摘要）+ 手动记录 |
| Dashboard | Webhook 数据接收 | 外部系统（ERP/电商）JSON 数据推送接收与存储，`POST /api/webhook/data` |
| Dashboard | 文件上传解析 | Excel/CSV/JSON/TXT/MD 上传 + 智能解析为结构化数据，`POST /api/upload/parse` |
| Dream | SQLite 自动备份 | 每日 01:00 `sqlite3.backup()` 热备份，7 天滚动保留 |
| Channels | Feishu/WeCom | IM 渠道接入 |

## 需求说明

- **业务背景**：企业需要 AI 辅助管理团队日常运营（KPI 考核、任务调度、奖金计算），但所有 AI 决策必须可追溯、可挑战、可干预
- **用户角色**：T1（Boss）全权限 / T2（Manager）部门级 / T3（Employee）IM + 绑定 `employee_id` 后可使用 `/my` 自助工作台
- **核心需求**：AI 建议 → 人工审批 → 执行 → 可申诉的完整闭环

## 业务逻辑

### Safety Layer 数据流

```
Engine/Agent 发起动作
    │
    ▼
ApprovalGateway.submit()
    │
    ├─ Shadow? ─→ 写入 shadow_results，不执行
    │
    ├─ 解析 automation_level (profile + action_type)
    │
    ├─ 置信度降级 (C + L3→L2, C + L4→L3)
    │
    ├─ L1: 仅通知
    ├─ L2: 创建审批记录，等待人工决策
    ├─ L3: 先执行，后汇报
    └─ L4: 静默执行
```

### 申诉流程

```
filed → evidence_collected → ruling → resolved / overturned
```

### Dream Engine 夜间流程

```
02:00 MemoryDistiller → 按员工聚合昨日对话 → LLM 摘要 → memories (L5)
03:00 KnowledgeExtractor → 任务/KPI/长反馈/已复盘决策 → knowledge (candidate)
06:00 ReportGenerator → stats_json + LLM summary → dream_reports → push（若配置 webhook / open_id）
```

## 技术架构

```
┌─────────────┐  ┌─────────────┐  ┌───────────────┐
│  Dashboard   │  │  Channels   │  │   Scheduler   │
│  (FastAPI)   │  │ Feishu/WeCom│  │ (APScheduler) │
└──────┬───────┘  └──────┬──────┘  └───────┬───────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌─────────────────────────────────────────────────┐
│              Runtime (Agent Loop / LLM)          │
├─────────────────────────────────────────────────┤
│              Engines (KPI/Task/Goal/Calc)        │
├─────────────────────────────────────────────────┤
│   Safety Layer (Approval / Shadow / Dispute)     │
├─────────────────────────────────────────────────┤
│   Infra (EventBus / Memory / Permission / Audit) │
├─────────────────────────────────────────────────┤
│          Core (DB / Models / Enums / Config)      │
└─────────────────────────────────────────────────┘
```

**技术栈**：Python 3.12+ / FastAPI / SQLite(WAL) / Pydantic v2 / LiteLLM / Jinja2

**安全加固（v7.3.0）**：
- Safety 层 EventBus 已从桩函数接入真实实例
- 公式求值强制依赖 simpleeval（禁用 `eval()` fallback）
- 数据网关列名正则校验（防 SQL 注入）
- 文件解析器路径白名单（防路径遍历）
- 时间戳统一使用 `datetime.now(timezone.utc)`（时区感知）

## 项目结构

```
qfbj/
├── app/
│   ├── core/           # 数据模型、枚举、数据库、配置、异常、本地上传（uploads.py）
│   ├── infra/          # 事件总线、记忆、权限、审计、Hook
│   │   ├── audit.py       # F31: AuditWriter 异步批量写入
│   │   ├── eventbus.py    # F29: EventBus (asyncio.Queue pub/sub)
│   │   ├── hooks.py       # F30: HookEngine 事件→条件→动作
│   │   ├── memory.py      # F27: MemoryDispatcher 5 层记忆
│   │   └── permission.py  # F28: T1/T2/T3 + P0-P4 权限校验
│   ├── safety/         # 审批网关、影子模式、申诉中心
│   │   ├── approval.py   # F44: ApprovalGateway
│   │   ├── shadow.py     # F45: ShadowModeService
│   │   └── dispute.py    # F46: DisputeCenter
│   ├── engines/        # 业务引擎（全部继承 EngineBase）
│   │   ├── base.py        # EngineBase — DB 包装 + 审计日志
│   │   ├── task.py        # F17: 任务引擎
│   │   ├── kpi.py         # F18: KPI 引擎
│   │   ├── goal.py        # F19: 目标管理
│   │   ├── escalation.py  # F20: 升级引擎
│   │   ├── calc.py        # F21: 公式计算 + 奖金联动
│   │   ├── hiring.py      # F40: 招聘模块
│   │   ├── decision.py    # F41: 决策记录
│   │   ├── customer.py    # F42: 客户记忆
│   │   └── cross_team.py  # F43: 跨团队依赖
│   ├── runtime/        # Agent 运行时
│   │   ├── agent_loop.py    # F06: 9-state 循环（IDLE→RESPONDING）
│   │   ├── context.py       # F07: 7 维上下文 + 80% 压缩
│   │   ├── llm.py           # F08: litellm 统一调用
│   │   ├── model_router.py  # F09: 模型选择 + 预算 + 降级
│   │   ├── sub_agent.py     # F10: 4 角色子代理
│   │   └── prompt_engine.py # F11: 系统提示词渲染
│   ├── channels/       # Feishu/WeCom 消息适配
│   │   ├── router.py      # F22: 统一入站消息路由
│   │   ├── feishu.py      # F23: 飞书 webhook + Bot API
│   │   ├── wecom.py       # F24: 企微 WebSocket 长连接
│   │   ├── bot_manager.py # F25: Bot 凭证管理 + 路由表
│   │   └── notification.py# F26: 事件驱动通知 + 智能合并
│   ├── dashboard/      # Web 管理后台 + API
│   │   ├── app.py        # F36: 路由注册、Jinja2、全局上下文
│   │   ├── ui_labels.py  # 27 个 zh_* Jinja 过滤器：状态/类型/等级/角色/渠道/资源类型/事件类型全中文化
│   │   ├── auth.py       # F36: 登录/登出、bcrypt、签名 Cookie、Tier 鉴权
│   │   ├── wizard.py     # F36: 3 步引导向导 + 自动创建 Boss Agent
│   │   ├── ws.py         # F38: WebSocket 实时聊天 + 智能面板
│   │   ├── api/
│   │   │   ├── overview.py    # P01: 总览页
│   │   │   ├── teams.py       # P02+P03: 团队列表/详情（含日报模板）
│   │   │   ├── employees.py   # 员工管理 + 辅导记录
│   │   │   ├── my.py          # 员工自助 /my
│   │   │   ├── commands.py    # P04: 快捷指令
│   │   │   ├── approval.py    # P05: 审批中心（双栏布局）
│   │   │   ├── tasks.py       # P06: 任务管理
│   │   │   ├── kpi.py         # P07: KPI 管理 + /kpi/scores 评分记录
│   │   │   ├── salary.py      # 薪酬计算 /salary
│   │   │   ├── escalation.py  # P08: 升级处理
│   │   │   ├── dispute.py     # P09: 申诉中心（双栏布局）
│   │   │   ├── knowledge.py   # P10: 知识库
│   │   │   ├── memory.py      # P11: 记忆管理 (L1-L5)
│   │   │   ├── models.py      # P12: 模型管理 + 用量统计
│   │   │   ├── hiring.py      # P14: 招聘管理（画像/候选人）
│   │   │   ├── decisions.py   # P15: 决策日志（列表/详情/记录）
│   │   │   ├── chat.py        # POST /api/chat — Agent 对话（JSON）
│   │   │   ├── webhook.py     # 外部数据 Webhook 接收
│   │   │   └── upload.py      # 文件上传 + 智能解析
│   │   └── templates/
│   │       ├── base.html         # 5 级侧边栏 + 4 层页面结构
│   │       ├── login.html        # 登录页
│   │       ├── wizard/           # step1–step3.html（3 步向导）
│   │       ├── pages/            # 管理页 + 员工自助 my_*.html（KPI 评分、薪酬等）
│   │       └── partials/         # HTMX 局部渲染片段
│   ├── skills/         # 工具/技能系统
│   │   ├── sdk.py         # F12: @tool 装饰器 + ToolCall/ToolResult
│   │   ├── registry.py    # F16: 统一 Skill 注册中心
│   │   ├── skill_md.py    # F14: SKILL.md 解析器
│   │   ├── mcp_client.py  # F15: MCP 客户端
│   │   └── builtin/       # F13: 内置技能
│   │       ├── sqlite_data.py  # 数据网关
│   │       ├── knowledge.py    # BM25 知识搜索
│   │       ├── file_parser.py  # 文件解析
│   │       ├── calc_engine.py  # 公式引擎
│   │       ├── notification.py # 通知技能
│   │       ├── feishu_im.py      # 飞书 IM
│   │       ├── feishu_bitable.py # 飞书多维表格（Bitable）
│   │       └── wecom_im.py       # 企微 IM
│   ├── dream/          # Dream 引擎（夜间复盘与学习）
│   │   ├── distiller.py   # F32: 对话 LLM 蒸馏
│   │   ├── extractor.py   # F33: 知识提取
│   │   ├── reporter.py    # F34: 报告生成 + LLM 摘要
│   │   ├── push.py        # 报告推送飞书/企微
│   │   ├── templates.py   # F35: 模板引擎
│   │   └── scheduler.py   # APScheduler 定时编排
│   └── main.py         # FastAPI 入口
├── data/
│   └── migrations/     # SQL 迁移脚本
├── scripts/            # 运维脚本（含 nginx.conf 生产部署配置）
├── tests/              # 测试
└── requirements.txt
```

## 环境配置

通过环境变量或 `config.yaml` 配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QFBJ_DB_PATH` | SQLite 数据库路径 | `data/qfbj.db` |
| `QFBJ_HOST` | 监听地址 | `0.0.0.0` |
| `QFBJ_PORT` | 监听端口 | `8000` |
| `QFBJ_DEBUG` | 调试模式 | `false` |
| `QFBJ_ENCRYPT_KEY` | Fernet 密钥或口令（非标准格式时内部 SHA256 派生） | 内置固定默认值（生产务必修改） |
| `QFBJ_SECRET_KEY` | 仪表盘会话签名密钥 | `qfbj-dashboard-secret-change-in-production` |
| `QFBJ_LOG_LEVEL` | 日志级别 | `INFO` |
| `QFBJ_BACKUP_DIR` | 备份目录 | `data/backups` |
| `QFBJ_KNOWLEDGE_DIR` | 知识库目录 | `knowledge` |
| `QFBJ_MAX_AGENT_TURNS` | Agent 最大轮次 | `15` |
| `QFBJ_CONTEXT_COMPRESS_THRESHOLD` | 上下文压缩触发阈值 | `0.8` |
| `QFBJ_CONTEXT_KEEP_RECENT` | 压缩时保留最近轮次数 | `5` |
| `FEISHU_APP_ID` | 飞书应用 ID（团队未配 bot 时 webhook 回复兜底） | - |
| `FEISHU_APP_SECRET` | 飞书应用 Secret（同上） | - |
| `FEISHU_ENCRYPT_KEY` | 事件订阅 Encrypt Key；**未设置则跳过签名校验**（仅建议开发环境） | - |
| `FEISHU_VERIFICATION_TOKEN` | 飞书事件 Verification Token（配置项预留，与加密策略配合） | - |

**本地上传**：知识库文件上传与任务反馈附件写入 `data/uploads/`（启动时自动创建），并通过 `GET /uploads/...` 对外提供只读访问；单文件上限 20MB，允许扩展名见 `app/core/uploads.py` 中 `ALLOWED_EXTENSIONS`。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python -m app.main
# 或
uvicorn app.main:app --reload
```

## API 文档

启动后访问 `http://localhost:8000/docs` 查看自动生成的 OpenAPI 文档。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 存活检查；JSON 含 `status`、`version`（当前应用版本 **11.0.0**） |
| POST | `/api/chat` | JSON：`team_id`、`message` → `AgentLoop`；响应 `response` + `metadata`；需登录 Cookie，T2 仅能访问本人团队 |
| POST | `/api/webhook/data` | 外部系统数据推送（Header：`X-Source`、`X-Team-Id`、`X-API-Key`），Body：`{data_type, records[], metadata}` |
| GET | `/api/webhook/data` | 列出最近 100 条 webhook 数据接收记录 |
| POST | `/api/upload/parse` | 上传文件（multipart：`file`、`team_id`、`description`）并解析为结构化数据 |
| GET | `/api/uploads` | 列出已上传文件 |

**T2 范围**：上述 HTML 路由在 T2 登录时按 `request.state.user_teams`（来自 `dashboard_users.employee_id` → `employees.team_id`）过滤列表与写操作；无绑定团队时 `user_teams` 为空列表，列表多为空且无法越权读写他团队数据。T2 另允许以 `/api` 为前缀的 JSON API（含 `POST /api/chat`），服务端仍校验 `team_id ∈ user_teams`。

**成功提示**：多数 POST 成功重定向会在 URL 上带 `?msg=…`（UTF-8 百分号编码）；`base.html` 自动弹出绿色 Toast 并从地址栏移除 `msg`。

### Dashboard 任务管理（HTML 表单）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | 任务列表 |
| POST | `/tasks` | 创建任务 |
| GET | `/tasks/{id}` | 任务详情 |
| POST | `/tasks/{id}/status` | 更新状态（`status` 表单字段；设为 `completed` 时写入 `completed_at`） |
| POST | `/tasks/{id}/feedback` | 追加反馈（`content` → `task_feedbacks`，`feedback_type=text`） |
| POST | `/tasks/{id}/feedback-file` | 附件反馈（`multipart`：`file` 必填，`content` 可选 → `task_feedbacks`，`feedback_type=file`，`file_path` 存磁盘路径） |
| POST | `/tasks/{id}/score` | 手动评分（仅 `submitted`；三维分数 + 等级 + 评语，均分写入 `score`，状态改为 `scored`） |
| POST | `/tasks/{id}/delete` | 删除任务（级联清理反馈、升级记录、任务依赖） |

### Dashboard 知识库（HTML 表单）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge` | 知识列表（支持 `category` / `scope` / `status` 查询参数；`upload_error` 为上传失败提示） |
| POST | `/knowledge` | 创建文本知识（`title`、`content`、`category`、`scope`、`department`） |
| POST | `/knowledge/upload` | 上传文件为知识（`multipart`：`file`、`title`、`category`、`scope`、`department`）；内容字段为摘要 + `文件路径: /uploads/{存储文件名}` |
| GET | `/knowledge/pending` | 待审知识与 Dream 候选 |

静态访问：已上传文件通过 `GET /uploads/{文件名}` 提供（文件保存在 `data/uploads/`）。

### Dashboard 模型 / 指令 / 团队（HTML 表单）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/models` | 模型列表 |
| POST | `/models` | 注册模型 |
| POST | `/models/{id}/update` | 更新配置（可选 `api_key` 非空时重新加密写入） |
| POST | `/models/{id}/delete` | 删除模型 |
| POST | `/models/{id}/toggle` | 切换启用/禁用 |
| POST | `/models/{id}/test` | API Key 探测（JSON） |
| GET | `/commands` | 指令列表 |
| POST | `/commands` | 创建自定义指令 |
| POST | `/commands/{id}/delete` | 删除自定义指令（内置指令忽略） |
| POST | `/commands/{id}/toggle` | 切换启用 |
| PUT | `/commands/{id}` | JSON 更新（API） |
| POST | `/teams/{id}/publish` | 发布团队（`status=active`） |
| POST | `/teams/{id}/report-template` | 新建团队日报/周/月报模板（`name`、`template_content`、`report_type`） |

### Dashboard 设置向导（HTML，无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wizard/step1` … `/wizard/step3` | 3 步页面；`step1` 输入公司名称，`step2` 配置 LLM（含已有 `models` 列表），`step3` 配置飞书机器人 |
| POST | `/wizard/step1` | 保存公司名称到 Cookie，302 至 step2 |
| POST | `/wizard/step2` | 写入模型配置（去重），302 至 step3 |
| POST | `/wizard/step3` | 自动创建 Boss Agent（`is_boss_agent=1`，`data_scope='*'`）+ 绑定飞书机器人，清除 `wizard_*` Cookie；302 至 `/?msg=…` 或 `/login?msg=…` |

登录页与总览页支持查询参数 `msg`：绿色提示条展示向导完成等文案。

### 员工自助 /my（HTML，T3 默认入口）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/my` | 工作台：任务与 KPI 摘要、团队信息、申诉表单（需绑定 `dashboard_users.employee_id`） |
| GET | `/my/tasks` | 我的任务；`dispatched`/`in_progress` 可「标记完成」→ `submitted` |
| GET | `/my/kpi` | 我的 KPI 得分（关联指标名称） |
| POST | `/my/tasks/{id}/submit` | 员工提交任务 |
| POST | `/my/dispute` | 提交申诉（`type`、`target_type`、`target_id`、`employee_reason`） |

### 员工与辅导（HTML）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/employees/{id}/coaching` | 新增辅导记录（`content`、`tags`；`coach_id` 为当前用户 `employee_id` 或用户 `id`） |

### Dashboard KPI 评分与薪酬（HTML 表单）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/kpi/scores` | KPI 评分历史：可按 `team_id`、`employee_id`、`period_key`（YYYY-MM）筛选 |
| POST | `/kpi/scores` | 手动录入/更新评分（`kpi_def_id`、`employee_id`、`period_key`、`total_score`、`grade` A–D、`feedback`） |
| GET | `/salary` | 薪酬计算列表：可按团队、周期、状态筛选；展示关联 `reward_rules` |
| POST | `/salary/calculate` | 按 `team_id` + `period` 批量计算：匹配 KPI 等级与规则，写入 `reward_calculations`（仅覆盖同团队同周期且 `status=calculated` 的记录） |

### Dashboard 审批中心（HTML 表单）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/approvals` | 审批列表（支持 `status`、`confidence`、`type`、`urgency` 筛选；`msg` 查询参数展示操作提示） |
| GET | `/approvals/{id}` | 审批详情（HTMX 请求返回右侧详情 partial） |
| POST | `/approvals/batch-approve` | 批量通过（表单 `ids`：逗号分隔的审批 ID，仅处理 `pending`） |
| POST | `/approvals/batch-reject` | 批量拒绝（表单 `ids`、`reason`，默认原因「批量驳回」） |
| POST | `/approvals/{id}/approve` | 单条通过 |
| POST | `/approvals/{id}/reject` | 单条拒绝（表单 `reason` 必填） |

### Safety Layer API（内部服务）

| 服务 | 方法 | 说明 |
|------|------|------|
| `ApprovalGateway` | `submit()` | 提交动作请求，自动路由到 L1-L4 |
| `ApprovalGateway` | `approve()` / `reject()` | 审批或驳回 |
| `ApprovalGateway` | `withdraw()` | 撤回待审批请求 |
| `ApprovalGateway` | `list_pending()` | 查询团队待审批列表 |
| `ApprovalGateway` | `get_stats()` | 审批状态统计 |
| `ShadowModeService` | `start_shadow()` / `switch_to_live()` | 影子模式切换 |
| `ShadowModeService` | `generate_report()` | 生成影子期分析报告 |
| Dashboard | `POST /disputes` | 提交申诉（表单：`dispute_type`、`target_id`、`reason`） |
| Dashboard | `POST /disputes/{id}/evidence` | 追加证据（表单：`content`、`evidence_type`） |
| `DisputeCenter` | `file_dispute()` | 提交申诉 |
| `DisputeCenter` | `add_evidence()` | 追加证据 |
| `DisputeCenter` | `resolve()` / `overturn()` | 裁决/推翻 |
| `DisputeCenter` | `suggest_rule_correction()` | AI 建议规则修正 |

### Business Engine API（内部服务）

| 引擎 | 方法 | 说明 |
|------|------|------|
| `TaskEngine` | `create_task()` | 创建任务 |
| `TaskEngine` | `dispatch_task()` | 分派任务 |
| `TaskEngine` | `submit_feedback()` | 提交反馈 |
| `TaskEngine` | `score_task()` | 三维评分（及时性40%+质量40%+复杂度20%） |
| `TaskEngine` | `complete_task()` | 完成任务 |
| `TaskEngine` | `get_overdue_tasks()` | 查询逾期任务 |
| `KPIEngine` | `create_kpi_definition()` | 创建 KPI 定义 |
| `KPIEngine` | `score_employee()` | 计算员工 KPI 综合评分 |
| `KPIEngine` | `generate_improvement_suggestion()` | 生成改进建议 |
| — | `auto_score_system_kpis()` | 系统类 KPI 按员工+周期自动算分并写入/更新 `kpi_scores` |
| `GoalEngine` | `create_goal()` | 创建目标 |
| `GoalEngine` | `cascade_goal()` | 级联分解目标 |
| `GoalEngine` | `update_progress()` | 更新进度（自动检测达成） |
| `GoalEngine` | `get_goal_tree()` | 获取目标层级树 |
| — | `check_overdue_tasks()` | 批量：将新超期任务标为 `overdue`，按团队 `escalation_json` 写升级记录并发事件 |
| `EscalationEngine` | `list_tasks_past_deadline()` | 查询已过截止且未终态的任务（供渐进 `escalate`） |
| `EscalationEngine` | `check_overdue_tasks(team_id)` | 同上查询的兼容别名 |
| `EscalationEngine` | `escalate()` | 按超期分钟与已有级别创建下一级升级（含老板级审批） |
| — | `detect_anomalies()` | 异常模式 → 待审批 `risk_alert` |
| `CalcEngine` | `evaluate_formula()` | 安全公式求值 |
| `CalcEngine` | `calculate_reward()` | KPI 奖金计算 |
| `CalcEngine` | `create_reward_rule()` | 创建奖金规则 |
| `CrossTeamEngine` | `create_dependency()` | 创建依赖 |
| `CrossTeamEngine` | `on_task_completed()` | 完成后解锁下游 |
| `CrossTeamEngine` | `get_bottleneck_report()` | 瓶颈分析 |
| `HiringEngine` | `create_hiring_profile()` | 生成招聘画像 |
| `HiringEngine` | `generate_jd()` | 生成 JD |
| `HiringEngine` | `score_candidate()` | 候选人评分 |
| `HiringEngine` | `create_onboarding_plan()` | 入职计划 |
| `DecisionEngine` | `record_decision()` | 记录决策 |
| `DecisionEngine` | `track_metrics()` | 快照指标 |
| `DecisionEngine` | `review_decision()` | 前后对比复盘 |
| `CustomerEngine` | `create_customer()` | 创建客户 |
| `CustomerEngine` | `transfer_customer()` | 转移客户 |
| `CustomerEngine` | `check_churn_risk()` | 流失预警 |

### Skill System API（内部服务）

| 服务 | 方法 | 说明 |
|------|------|------|
| `@tool` | 装饰器 | 注册函数为可调用工具，自动权限检查+审计 |
| `execute_tool()` | 执行工具 | 按 ToolCall 查找并执行工具 |
| `SkillRegistry` | `register_builtin_skills()` | 扫描 @tool 注册内置技能 |
| `SkillRegistry` | `get_tools_for_team()` | 查询团队可用工具列表 |
| `SkillRegistry` | `assign_skill_to_team()` | 将技能分配给团队 |
| `sqlite_data__query` | 数据查询 | 自动注入 DataScope 行过滤 |
| `sqlite_data__insert` | 数据插入 | P2+ 权限，自动注入 team_id |
| `sqlite_data__update` | 数据更新 | P2+ 权限，行级访问验证 |
| `sqlite_data__delete` | 数据删除 | P3+ 权限，敏感操作 |
| `knowledge__search` | 知识搜索 | BM25 + jieba 中文分词 |
| `calc_engine__evaluate` | 公式求值 | simpleeval 沙箱模式 |
| `notification__merge_and_send` | 智能通知 | 重要立即/普通5分钟合并 |
| `feishu_bitable__create_table` | 多维表格建表 | P2；`fields` 为 JSON 字段定义数组 |
| `feishu_bitable__append_records` | 批量追加记录 | P2；`records` 为 JSON |
| `feishu_bitable__query_records` | 查询记录 | P1；可选 `filter_expr`、分页 |
| `feishu_bitable__list_tables` | 列出数据表 | P1 |

### Runtime API（内部服务）

| 服务 | 方法 | 说明 |
|------|------|------|
| `AgentLoop` | `run()` | 处理单条消息：9 状态机循环，per-employee 锁串行处理 |
| `ContextManager` | `load()` | 加载 7 维上下文（身份/员工/历史/记忆/知识/状态/目标） |
| `ContextManager` | `to_messages()` | 将 ContextPayload 转为 LLM 消息列表 |
| `LLMClient` | `complete()` | 非流式调用（指数退避自动重试） |
| `LLMClient` | `stream()` | 流式调用 |
| `LLMClient` | `count_tokens()` / `count_text_tokens()` | token 计数 |
| `LLMClient` | `get_context_window()` | 获取模型上下文窗口大小 |
| `ModelRouter` | `select_model()` | 选择最优模型（主→备→系统默认） |
| `ModelRouter` | `select_model_for_sub_agent()` | 子代理模型选择（支持 override） |
| `ModelRouter` | `record_usage()` | 记录 token 用量 + 80/90/95% 预算告警 |
| `ModelRouter` | `get_daily_usage()` | 查询当日模型用量 |
| `SubAgentRunner` | `invoke()` | 调用子代理（权限隔离，max=min(parent, role_cap, db_cap)） |
| `SubAgentRunner` | `invoke_analyst()` | 便捷方法：调用分析师子代理（P0 只读） |
| `SubAgentRunner` | `invoke_coach()` | 便捷方法：调用教练子代理（P0 建议） |
| `SubAgentRunner` | `invoke_executor()` | 便捷方法：调用执行者子代理（P2 执行） |
| `PromptEngine` | `render()` | 变量插值（缺失变量段落自动跳过） |
| `PromptEngine` | `build_variables()` | 组装标准变量字典 |

### Channel System API（内部服务）

| 服务 | 方法 | 说明 |
|------|------|------|
| `BotManager` | `register_bot()` | 注册/更新 Bot 凭证（Fernet 加密） |
| `BotManager` | `get_credentials()` | 获取解密凭证 |
| `BotManager` | `test_connection()` | 验证凭证有效性 |
| `BotManager` | `hot_reload()` | 热重载凭证和路由表 |
| `NotificationService` | `start()` | 订阅 EventBus + 启动合并 flush |
| `EventBus` | `emit()` / `subscribe()` | 异步事件发布/订阅 |
| `HookEngine` | `add_rule()` / `process_event()` | 管理和执行 Hook 规则 |
| `MemoryDispatcher` | `load_for_scenario()` | 按场景加载 5 层记忆 |
| `AuditWriter` | `write()` / `flush_now()` | 非阻塞审计写入 |

### Dream Engine API（内部服务）

| 服务 | 方法 | 说明 |
|------|------|------|
| `MemoryDistiller` | `distill_conversations()` | 按日 LLM 蒸馏对话 → L5 |
| `KnowledgeExtractor` | `extract_knowledge_candidates()` | 任务/KPI/长反馈/已复盘决策 → 知识候选 |
| `ReportGenerator` | `generate_*_report()` | 报告 `summary` 为 LLM 正文（失败回落统计短文案） |
| `push_report_sync` / `push_report_to_im` | `app.dream.push` | 按 `team_bots` 推送报告 |
| `TemplateEngine` | `render_template()` | 渲染通知/报告模板 |
| `dream.scheduler` | `setup_dream_scheduler()` | DB 备份 01:00（7 天保留）、蒸馏 02:00、知识 03:00、日报 06:00、周报周日 06:00、月报每月 1 日 06:00；超期/渐进升级 每 30 分钟；审批过期清理 每 30 分钟；KPI 23:00；异常与留存 09:00 |

## 环境配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QFBJ_DB_PATH` | SQLite 数据库路径 | `data/qfbj.db` |
| `QFBJ_HOST` | 监听地址 | `0.0.0.0` |
| `QFBJ_PORT` | 监听端口 | `8000` |
| `QFBJ_DEBUG` | 调试模式 | `false` |
| `QFBJ_LOG_LEVEL` | 日志级别 | `INFO` |
| `QFBJ_ENCRYPT_KEY` | Fernet 密钥或口令（非标准格式时内部派生） | 内置固定默认值（生产务必修改） |
| `QFBJ_SECRET_KEY` | 仪表盘会话签名 | `qfbj-dashboard-secret-change-in-production` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `FEISHU_APP_ID` | 飞书应用 ID（团队未配 bot 时 webhook 回复兜底） | - |
| `FEISHU_APP_SECRET` | 飞书应用 Secret（同上） | - |
| `FEISHU_ENCRYPT_KEY` | 事件 Encrypt Key；未设置则 webhook 不校验签名 | - |
| `FEISHU_VERIFICATION_TOKEN` | Verification Token（预留） | - |

## 快速开始

### 1. 本地开发

```bash
cd qfbj
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 初始化数据库 + 创建默认管理员
python scripts/init_db.py

# 启动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000/login，默认账号 `admin` / `admin123`。

### 2. 服务器部署 (systemd)

```bash
# 上传代码到服务器
scp -r qfbj ubuntu@YOUR_SERVER:/home/ubuntu/

# SSH 到服务器
ssh ubuntu@YOUR_SERVER

# 安装依赖
cd /home/ubuntu/qfbj
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 初始化数据库
python scripts/init_db.py

# 创建 systemd 服务（参考 qfbj.service）
sudo cp /path/to/qfbj.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable qfbj
sudo systemctl start qfbj
```

### 3. Docker 部署

```bash
docker compose up -d --build
```

### 4. 植入测试数据

```bash
cd /home/ubuntu/qfbj
./venv/bin/python scripts/seed_data.py
```

脚本幂等执行，植入千帆海公司完整测试数据（6团队/19员工/12任务/10KPI/3审批/3客户/5知识）。

## 当前部署状态

| 项目 | 状态 |
|------|------|
| 服务器 | `159.75.48.163:8000` |
| 部署方式 | systemd (python + uvicorn) |
| 数据库 | SQLite WAL, 37 张表 |
| 测试数据 | 千帆海公司（6团队/19员工/12任务/10KPI/3审批） |
| 应用版本 | 10.2.0（`/health` 返回 `version`） |
| 定时任务 | APScheduler（DB 备份 01:00、蒸馏 02:00、知识提取 03:00、日报 06:00 + 周日 06:00 周报 + 每月 1 日 06:00 月报、超期+渐进升级每 30 分钟、审批过期清理每 30 分钟、系统 KPI 23:00、异常与留存 09:00） |
| 默认账号 | admin / admin123 |

## 文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 使用教程 | `docs/使用教程.md` | 15章节完整操作指南 + 5个日常场景 |
| 测试用例 | `docs/测试用例.md` | 15大类 40+ 测试用例 + 自动化命令 |
| 重构方案 | `千方百计AI重构方案V3.md` | 架构设计全文档 |
| 变更日志 | `CHANGELOG.md` | 版本历史 |

## 测试说明

```bash
# 单元测试
pytest tests/ -v

# 自动化接口验证（参见 docs/测试用例.md 底部的 curl 命令）
curl -s http://159.75.48.163:8000/health
```
