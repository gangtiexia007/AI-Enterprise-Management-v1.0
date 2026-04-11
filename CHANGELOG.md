# 更新日志

## [2026-04-12] - POD 3.0 P1/P2 自动化全量上线（v8.0）

### P1 新增功能
- **周一三问周报任务**：每周一 09:30 自动为每位运营创建"三问周报"飞书任务并推送通知（上周链接/最佳产品/本周方向/问题反馈）
- **周二KPI排名推送**：每周二 10:30 自动聚合上周运营 KPI 排名，以飞书卡片推送给老板/主管
- **月度Goal自动创建**：每月 1 日自动为每位运营按出单量/销售额/有效链接数创建月度目标，导入订单时实时更新 `current_value`
- **AI赛道补分类**：每日 03:00 批量调 AI 对关键词未命中（约 40%）的产品标题进行赛道分类，写入 `niche` 字段

### P2 新增功能
- **月度复盘自动化**：每月 1 日 09:00 聚合上月 KPI 与上上月对比，生成结构化复盘排名并推飞书
- **淘汰/奖励预警**：
  - 连续 2 月垫底 → 飞书告警老板
  - 连续 3 周未提交三问周报 → 飞书提醒当事人 + 通知老板
  - 月度第一 → 飞书通知老板表彰
- **AuditLog 全链路审计**：订单/产品导入操作写入 AuditLog（actor/action/detail/resource_type）
- **月度Goal同步**：上传订单时自动触发本月 Goal `current_value` 更新

### 技术细节
- `pod_order_rules.py` 新增：`sync_monthly_goals`、`run_monthly_review`、`check_elimination_and_rewards`、`run_ai_niche_classification`
- `scheduler.py` 新增 7 个定时任务：`weekly_three_questions`、`weekly_kpi_ranking_report`、`monthly_goals_update`、`monthly_review_push`、`elimination_alert_check`、`ai_niche_batch`
- `pod_orders.py` upload 端点增加 AuditLog 写入 + Goal 自动同步

---

## [2026-04-11] - POD 3.0 绩效系统集成

### 新增数据模型
- `PodOrder`：ERP 订单数据模型（28+字段），支持运营归属自动提取、货币换算、状态分类、赛道分类
- `PodProduct`：ERP 产品数据模型，支持选品命中率追踪

### 新增后端接口（/api/pod）
- `POST /upload-orders`：订单 Excel 上传解析（按列名动态映射、去重、运营提取、汇率换算、赛道分类）
- `POST /upload-products`：产品 Excel 上传解析（店铺名提取运营、赛道分类）
- `GET /stats`：订单/产品基础统计
- `GET /operator-kpi`：运营 KPI 排名（出单量、销售额、取消率、命中率）
- `GET /niche-stats`：赛道维度统计（出单量、SKU 数、运营分布）
- `GET /sku-grading`：SKU 自动分级（S/A/B/C/D）

### 新增业务规则引擎（pod_order_rules.py）
- `run_sku_grading`：按 SKU 聚合出单量自动分级（S/A/有效链接/C）
- `run_operator_kpi`：按运营聚合 KPI（按国家/平台拆分）
- `run_hit_rate`：选品命中率计算（产品表与订单表交叉匹配）
- `run_daily_upload_stats`：每日上新数量统计
- `sync_kpi_records`：自动写入 KPIRecord 激活现有告警/辅导/评分链路

### 新增定时任务
- 每日 00:30 自动更新汇率（fawazahmed0/exchange-api）
- 每日 11:00 刷新产品出单状态
- 每周二 10:00 聚合上周 KPI 并写入 KPIRecord

### 赛道自动分类
- 关键词映射表优先（13 个赛道、80+ 关键词，约 60% 覆盖率）
- 未匹配标题可后续用 AI 补分类

### 前端新增运营绩效页面（/pod-performance）
- Tab 1：数据上传（订单 + 产品 Excel 拖拽上传）
- Tab 2：运营排名看板（出单量、销售额、取消率、命中率）
- Tab 3：赛道概览（各赛道出单量、SKU 数、运营分布）

### 现有功能增强
- `daily_report` / `data_summary` 补充今日订单量和 GMV 数据
- KPI 数据自动流入现有 coaching_suggestions、check_kpi_alerts、employee_score

---

## [2026-04-11] - UI 精简：删除 Agent 概览 + 任务创建改为自然语言

### 删除 Agent 概览 tab

- 移除 `Agent.tsx` 中的 `AgentOverview` 组件（运行模式、模型配置、系统 Prompt 与系统设置完全重复）
- Agent 管理页面默认展示 Skills 管理 tab
- 运行模式配置移至系统设置 → 基础设置（`agent_mode` 字段）

### 任务创建改为自然语言

- 移除手动创建任务的表单 Modal（标题/描述/负责人/优先级/截止日期等字段）
- 替换为自然语言输入框，用户输入如"给小王分配选品研究任务，下周三截止"，由 AI Agent 通过 `create_task` 技能自动解析并创建
- 保留任务的派发、完成、删除等操作按钮

---

## [2026-04-10] - 全面优化：Agent Harness 融合 + 系统精简 + Bug 修复

### 紧急修复 (HOTFIX)

- **修复指挥中心白屏**：`MultiAgentDashboard.tsx` 的 `parseAgentsCalled` 函数无法处理后端返回的数组类型 `agents_called`，导致 `TypeError` 崩溃整个 React 树。修复为兼容 `string | string[]` 两种类型。
- **修复 scheduler.py datetime 导入缺失**：`_run_coaching_suggestions` 函数中使用 `datetime.utcnow()` 但未导入 `datetime`，每周五 18:00 定时任务会 `NameError`。
- **修复 Agent 开关不落库**：`MultiAgentConfig.tsx` 的启用/禁用开关只改前端 state，刷新即失效。新增 `PUT /multi-agent/config/{agent_id}` 后端端点，前端切换时调用 API 持久化到 Setting 表。

### 核心架构改造

- **P0: BaseAgent tool-use loop**：将多 Agent 的 `_base_run` 从纯文本 `ai_client.chat()` 改为完整的工具调用循环，复用 `skill_registry`（30+ 技能）+ `permission_gateway`（P0-P4 权限）+ `hook_manager`（审计日志）。16 个 Agent 声明的 `allowed_tools` 现在真正生效。
- **P1: 记忆系统统一 (3→1)**：将 `knowledge`、`memory_entries`、`agent_memory_entries` 三张表合并为统一的 `knowledge` 表，新增 `level`、`platform`、`market`、`niche` 等字段。`memory_manager` 和 Multi-Agent API 全部改为查/写 `knowledge` 表。
- **P2: 上下文压缩 + Memory 接入**：Orchestrator 执行前加载 L3 知识 + L4 模式注入 Agent 上下文；链式执行中前序 Agent 输出超过 2 个时自动压缩摘要；执行后将 `memory_writeback` 回写 Knowledge 表。
- **P3: Token 统计**：`ai_client` 每次调用记录 `_last_usage_tokens`，`BaseAgent` 累加后设置到 `AgentOutput.total_tokens`，Orchestrator 汇总写入 `AgentRun.total_tokens`（不再是硬编码 0）。

### 基础设施补全

- **P5: 飞书智能路由**：`feishu_webhook.py` 新增 `_classify_agent_mode()` 函数，根据消息内容自动分流：`/` 开头走命令模式、POD 关键词走 `multi_agent`、其余走 `full`。`ChatDrawer.tsx` 新增模式切换按钮（通用模式/POD Agent）。
- **P6: 流式响应**：后端新增 `POST /api/agent/chat-stream` SSE 端点，前端 `ChatDrawer` 在 full 模式下使用流式接收逐字展示。
- **P7: 规则引擎联动**：`rules_engine` 检测到逾期/升级/KPI 低分时，额外写入 `rule_alert:*` 审计日志；Orchestrator 启动时查询最近 24h 的活跃告警注入 Agent 上下文。
- **P8: 定时任务联动**：`scheduler.py` 暴露 `get_scheduler()` 函数，`scheduled_tasks` 路由的 toggle 操作现在同时调用 APScheduler 的 `pause_job`/`resume_job`。
- **P9: P3 权限落实**：`permissions.py` 的 `check()` 方法 P3 级别从自动放行改为返回 `"pending_approval"`，`agent_loop.py` 检测到后自动创建 `Approval` 记录。

### 系统精简

- **P4: 删除旧 SubAgentManager**：删除 `sub_agents.py`、`SubAgentModel`、4 个 agent_admin 路由、前端子 Agent tab — 从未被实际使用过。
- **P10: 前端页面 19→13**：TaskDispatch 并入 Tasks、RiskControl 并入 ReviewSedimentation、NicheResearch+DataAttribution 合并为 AgentAnalysis、MultiAgentConfig 并入 Agent、OperatorScoreboard 并入 KPI。
- **P11: 后端路由合并**：`employees.py` + `coaching.py` + `teams.py` 合并为 `organization.py`。
- **P12: 清理死代码**：删除 Badge.tsx、DataTable.tsx、EmptyState.tsx、InfoBanner.tsx、ConfirmDialog.tsx 等未引用组件；删除 `context_manager.py` 中未使用的 `MAX_CONTEXT_TOKENS_ESTIMATE` 常量。

### 文档

- **P13: 文档规范化**：创建 `README.md`（完整项目描述）、`CHANGELOG.md`（本文件）、`.cursor/rules/documentation.md`（持久化文档维护规则）。
