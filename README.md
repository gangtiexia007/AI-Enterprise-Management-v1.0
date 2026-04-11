# 千方百计 AI 企业管理系统

> 老板的私人 AI 管理助手 — 基于多 Agent 协作的 POD 电商企业管理平台

## 功能概览

### 核心 AI 能力

- **17 Agent 集群**：A0 编排器 + 16 个专业 Agent（风控、商业分析、平台策略、市场人群、选品、设计、归因、利润、上新、优化、内容、任务调度、复盘、绩效、记忆管理）
- **Tool-Use 循环**：每个 Agent 可真正调用 30+ 注册技能（查询 Bitable、创建任务、发飞书消息等），而非纯文本生成
- **智能路由**：飞书消息根据内容自动分流到 POD 多 Agent 或通用单 Agent
- **流式响应**：前端对话支持 SSE 逐字输出
- **L1-L5 分层记忆**：工作记忆 → 摘要 → 知识库 → 模式蒸馏 → 归档，统一存储在 Knowledge 表
- **Token 预算管控**：日/月预算、80% 告警、90% 自动降级模型

### 企业管理功能

- **任务管理**：CRUD、派发、完成、逾期检测、多级升级催办、调度视图
- **目标管理**：树形目标分解、进度追踪
- **KPI 绩效**：评分计算、等级判定（S/A/B/C/D）、运营排行榜
- **审批流程**：创建、审批/驳回、超时提醒、P3 技能审批
- **辅导记录**：员工辅导建议、AI 自动生成
- **知识库**：SOP、案例、规则、禁忌分类管理

### 数据集成

- **飞书多维表格 (Bitable)**：员工、店铺、销售、财务等业务数据的读写
- **飞书机器人**：IM 消息收发、任务通知、日报/周报推送、催办提醒
- **飞书审批**：逾期任务自动创建审批

### 规则引擎

- 逾期任务检测与多级升级（员工提醒 → 老板通知 → 紧急标记）
- KPI 预警（低分自动通知）
- 审批超时检测（48h 提醒、72h 提优先级）
- POD 款式健康度评估（每日 10:00）

### 定时调度

- 周期检查（逾期/升级/KPI，可配置间隔）
- 日报推送（每日 09:00）
- 周报推送（每周一）
- 辅导建议（每周五 18:00）
- 记忆蒸馏（每日 02:00）
- Token 预算检查（每 6 小时）
- 审批超时检查（每 4 小时）
- KPI 告警检查（每 12 小时）
- POD 规则执行（每日 10:00）

## 需求说明

### 技术需求

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose（部署）
- OpenAI 兼容 API（模型服务）
- 飞书开放平台应用（App ID + App Secret）

### 业务需求

- 面向 POD（Print on Demand）电商企业
- 支持多平台（Temu、TikTok Shop、Shopee）
- 支持多市场（PH、SEA、EU、US）
- 单一管理者视角（老板/管理员）

## 业务逻辑

### Agent 处理流程

```
用户消息 → 智能路由（command/full/multi_agent）
  ├─ command: 斜杠命令直接执行，零 Token
  ├─ full: 单 Agent + 工具循环（通用管理）
  └─ multi_agent: A0 编排器 → 任务分类 → 数据门控 → Agent 链执行
       ├─ 每个 Agent 通过 skill_registry 调用工具
       ├─ permission_gateway 检查权限（P0-P4）
       ├─ hook_manager 记录审计日志
       ├─ 前序 Agent 输出自动压缩传递
       └─ 记忆回写到 Knowledge 表
```

### 6 条任务路由链

| 类型 | Agent 序列 |
|------|-----------|
| new_direction | A03→A01→A02→A05→A06→A04→A09→A10→A13→A14→A16 |
| link_analysis | A03→A01→A08→A04→A09→A11→A13→A14→A16 |
| market_expansion | A03→A02→A05→A06→A04→A09→A10→A13→A14→A16 |
| team_action | A03→A13 |
| content_event | A03→A05→A04→A12→A13→A14→A16 |
| review | A03→A14→A16 |

### 权限体系

| 级别 | 说明 | 行为 |
|------|------|------|
| P0 AUTO | 读取数据、查询统计 | 自动放行 |
| P1 RULE | 发通知、生成报告 | 规则放行 |
| P2 APPROVAL | 创建/修改任务、更新 KPI | 自动放行 |
| P3 STRONG_APPROVAL | 批量操作、删除数据 | 创建审批，需用户确认 |
| P4 FORBIDDEN | 系统配置变更 | 直接拒绝 |

## 项目结构

```
AI 企业管理/
├── app/
│   ├── backend/
│   │   ├── main.py                    # FastAPI 入口
│   │   ├── models.py                  # SQLAlchemy ORM 模型
│   │   ├── schemas.py                 # Pydantic 请求/响应 Schema
│   │   ├── database.py                # SQLite 数据库配置
│   │   ├── routers/
│   │   │   ├── agent.py               # 单 Agent 对话 + 流式端点
│   │   │   ├── agent_admin.py         # Agent 配置 + Skills 管理
│   │   │   ├── multi_agent.py         # 多 Agent API（chat/runs/config/memory）
│   │   │   ├── feishu_webhook.py      # 飞书事件回调 + 智能路由
│   │   │   ├── organization.py        # 员工 + 团队 + 辅导（合并）
│   │   │   ├── tasks.py               # 任务管理
│   │   │   ├── goals.py               # 目标管理
│   │   │   ├── kpi.py                 # KPI 绩效
│   │   │   ├── knowledge.py           # 知识库
│   │   │   ├── approvals.py           # 审批流程
│   │   │   ├── bitable.py             # 飞书多维表格
│   │   │   ├── reports.py             # 报表与统计
│   │   │   ├── settings.py            # 系统设置
│   │   │   ├── audit_logs.py          # 审计日志
│   │   │   └── scheduled_tasks.py     # 定时任务管理
│   │   └── harness/
│   │       ├── agent_loop.py          # 主 Agent 状态机
│   │       ├── ai_client.py           # OpenAI 兼容客户端
│   │       ├── skill_registry.py      # 统一技能注册中心
│   │       ├── memory_manager.py      # L1-L5 分层记忆
│   │       ├── context_manager.py     # 上下文窗口管理
│   │       ├── permissions.py         # P0-P4 权限网关
│   │       ├── hooks.py               # 生命周期钩子
│   │       ├── token_budget.py        # Token 预算管控
│   │       ├── rules_engine.py        # 业务规则引擎
│   │       ├── scheduler.py           # APScheduler 定时调度
│   │       ├── feishu_client.py       # 飞书 API 客户端
│   │       ├── bitable_client.py      # Bitable API 客户端
│   │       ├── pod_rules.py           # POD 业务规则
│   │       ├── prompt_templates.py    # 系统提示词模板
│   │       ├── mcp_client.py          # MCP 外部工具客户端
│   │       ├── multi_agent/
│   │       │   ├── orchestrator.py    # A0 编排器
│   │       │   ├── base_agent.py      # Agent 基类（tool-use loop）
│   │       │   ├── schemas.py         # AgentInput/Output 数据结构
│   │       │   ├── data_gate.py       # A3 数据充分性门控
│   │       │   ├── routes.py          # 路由链定义
│   │       │   └── agents/            # 16 个专业 Agent
│   │       └── skills/builtin/        # 30+ 内置技能
│   ├── frontend/
│   │   └── src/
│   │       ├── App.tsx                # 路由配置（13 页面）
│   │       ├── api/client.ts          # API 客户端函数
│   │       ├── components/
│   │       │   ├── Layout.tsx         # 侧栏导航布局
│   │       │   ├── ChatDrawer.tsx     # 全局 AI 对话抽屉（支持流式 + 多模式）
│   │       │   ├── Modal.tsx          # 通用弹窗
│   │       │   └── ui/               # 通用 UI 组件
│   │       └── pages/                 # 13 个页面
│   ├── docker-compose.yml             # Docker 编排
│   ├── deploy.sh                      # 部署脚本
│   └── nginx/                         # Nginx 配置
├── README.md                          # 本文件
├── CHANGELOG.md                       # 更新日志
└── .cursor/rules/documentation.md     # 文档维护规则
```

## 部署说明

### Docker Compose 部署

```bash
cd app
docker compose build --no-cache
docker compose up -d
```

### 环境配置

通过系统设置页面或 Settings API 配置：

| 配置项 | 说明 |
|--------|------|
| `ai_base_url` | AI 模型 API 地址 |
| `ai_api_key` | API Key |
| `ai_model_primary` | 主模型 |
| `ai_model_fallback` | 降级模型 |
| `feishu_app_id` | 飞书应用 ID |
| `feishu_app_secret` | 飞书应用密钥 |
| `feishu_boss_id` | 老板飞书 ID |
| `bitable_base_token` | 多维表格 Token |

### 服务架构

```
Nginx (80) → Frontend (React)
           → Backend (FastAPI :8000)
           → SQLite (harness.db)
```
