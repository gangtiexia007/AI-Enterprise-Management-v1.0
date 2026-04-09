# Changelog

All notable changes to 千方百计AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [11.2.0] - 2026-04-09

### Changed（变更）
- **Setup Wizard 从 7 步精简为 3 步**：公司名称 → 配置 LLM → 配置飞书机器人；移除组织模板选择、团队创建、员工添加等步骤
- **wizard.py 完全重写**：移除 ORG_TEMPLATES / step4-step7 路由，新增 step1 POST（保存公司名称 Cookie）、step2 POST（模型去重写入）、step3 POST（自动创建 Boss Agent + 绑定飞书 Bot）
- **wizard 模板全部替换**：step1-step3.html 使用 `base.html` 布局 + 内联进度条，不再依赖 `_progress.html`

### Added（新增）
- **TeamRegistry.create_boss_agent()**：自动创建 Boss Agent（`is_boss_agent=1`，`data_scope='*'`），幂等——已存在则直接返回
- **Boss Agent 默认系统提示词**：含全局运营管控、KPI 汇报、文件解析、任务分发等职责描述
- **feishu_bitable（F13）内置技能**：飞书多维表格 Open API — `feishu_bitable__create_table` / `__append_records` / `__query_records` / `__list_tables`（httpx，`tenant_access_token` 来自团队飞书 Bot 或环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`）

---

## [11.2.0] - 2026-04-09

### Added（新增）
- **飞书文件消息处理**：用户通过飞书发送文件/图片时，Bot 自动下载到 `data/uploads/` 并解析内容传递给 Agent
- **`download_feishu_file()`**：新增飞书文件下载函数（`app/channels/feishu.py`），支持 team_id 凭证路由和全局凭证兜底
- **`AgentLoop._parse_uploaded_file()`**：文件内容解析方法，支持 Excel（openpyxl）、CSV、TXT、MD、JSON 格式，预览前 20 行
- **飞书消息解析增强**：`_parse_message_event` 捕获 `file_name` 和 `file_type`，写入 `UnifiedMessage.raw`
- **文件消息路由**：`handle_feishu_event` 在路由前自动下载文件并填充 `msg.file_path`

### Changed（变更）
- `AgentLoop._run_locked` 在 LLM 调用前检测 `message.file_path`，自动解析文件内容拼入 `content`

---

## [Unreleased] - V3.8 架构决策

### Changed（变更）
- **多公司策略确定**：3 套独立 Fork 部署（千帆海/千万星河/千方百计科技），不做多租户
- **行业模板方案否决**：每家公司独立开发业务 Skill，不做通用模板引擎
- **"财务系统"重定义**：实为"数据搬运机器人"（Excel → AI 解析 → 飞书多维表格）
- **部门管理简化**：使用 employees.department 文本字段，不新建独立模块
- **架构文档升级至 V3.8**：记录所有决策、代码库组织方式、三公司业务差异

### Added（新增）
- **三公司独立代码库**：从 qfbj/ V11.1.0 fork 出 qfh-server/、qwxh-server/、qfbj-co-server/
- **CONTEXT.md × 3**：每个 fork 配套完整上下文文档，支持新 Cursor 窗口无缝开发
- **业务需求文档 × 3**：千帆海（跨境电商）、千万星河（软件销售）、千方百计科技（短视频IP）

---

## [11.1.0] - 2026-04-09

### Added（新增）
- **多轮对话摘要持久化**：AgentLoop._save_turn 在对话轮次超过 20 时自动生成摘要，保留最近 10 轮 + 历史摘要（最长 3000 字符）
- **对话历史摘要注入**：ContextManager._load_history 加载对话时自动将持久化摘要作为 system 消息注入上下文
- **工具参数 JSON Schema 生成**：SkillRegistry 使用 _params_from_func 从函数签名自动推导完整 JSON Schema（含类型、required、default）
- **CSV 文件解析工具**：file_parser__parse_csv — 支持自定义分隔符、编码、最大行数
- **外部数据 Webhook**：`POST /api/webhook/data` 接收 ERP/电商等外部系统 JSON 数据推送，`GET /api/webhook/data` 查看接收记录；接收后发布 `webhook.data_received` 事件
- **文件上传 + 智能解析**：`POST /api/upload/parse` 上传 Excel/CSV/JSON/TXT/MD 文件并自动解析为结构化数据，`GET /api/uploads` 查看上传历史；50MB 上限
- **SQLite 自动备份**：Dream Scheduler 每日 01:00 热备份（`sqlite3.backup()`），备份至 `data/backups/`，7 天滚动保留
- **WeCom 出站回复**：`WeComWSClient.send_message()` 通过 WebSocket 发送文本消息；`WeComManager.send_to_team()` 按 team_id 路由回复
- **统一出站路由**：`router.send_reply()` 按渠道（WeCom/Feishu）分发回复消息
- **Nginx 生产配置**：`scripts/nginx.conf` — 反向代理、WebSocket 支持、静态文件缓存、安全头
- **申诉提交路由**：`POST /disputes` 员工可通过仪表盘提交申诉；`POST /disputes/{id}/evidence` 追加证据
- **申诉弹窗表单**：申诉中心页面新增「提交申诉」按钮及 Alpine.js 弹窗

### Changed（变更）
- `_params_from_signature` 替换为 `_params_from_func`，支持更多类型注解（dict/list 泛型、默认值）
- T2 用户权限白名单扩展：新增 `/hiring`、`/customers`、`/decisions`、`/knowledge`、`/memory`、`/models`、`/salary`、`/commands`、`/uploads` 前缀

### Fixed（修复）
- Builtin Skills 启动时未加载：`register_builtin_skills()` 现在显式 import `app.skills.builtin` 确保 @tool 注册
- Webhook API Key 验证缺失：现在检查 team 的 `webhook_api_key` 字段
- 文件上传解析错误不可见：响应 JSON 现在包含 `error` 字段
- 申诉证据上传缺少登录检查
- 上下文压缩 `compress_if_needed` 对消息字段 `.get()` 安全访问，避免 KeyError
- 招聘页候选人评分为 0 时误显示为 `-`

## [11.0.0] - 2026-04-08

### Added（新增）
- **招聘管理仪表盘 (F40)**：新增 `/hiring`，职位画像 + 候选人管理（状态流转：待处理→筛选→面试→评分→Offer→入职/拒绝）
- **决策日志仪表盘 (F41)**：新增 `/decisions`，决策列表 + 详情页（数据依据、预期结果、复盘对比）
- **客户管理仪表盘 (F42)**：新增 `/customers`，客户列表 + 详情页（联系记录/反馈时间线）
- **AgentLoop 子 Agent 调用 (F10)**：新增 `invoke_sub_agent` 内置工具，LLM 可调用配置的子 Agent 完成专项任务
- **AgentLoop 上下文自动压缩**：第 2 轮起自动调用 `compress_if_needed` 压缩历史，避免超出 token 窗口
- **PromptEngine 系统提示词渲染 (F11)**：ContextManager.load 通过 PromptEngine 进行变量插值
- **MCP 工具 Schema 合并 (F15)**：SkillRegistry 自动包含 MCP 来源工具 schema
- **T3 员工 WebSocket 只读接入**：T3 用户可通过 WebSocket 连接，限定只访问自己所属团队
- **WeCom Bot 自动连接 (F24)**：启动时自动为已启用企业微信 Bot 建立 WebSocket 长连接
- **Jinja 过滤器扩展**：新增 `zh_review_status`、`zh_candidate_status` 中文化过滤器

### Changed（变更）
- **HookEngine 激活 (F30)**：启动时自动注册到 EventBus，启用事件→条件→动作管线
- **审批网关贯穿 (F44)**：任务创建/升级审批均通过 ApprovalGateway.submit() 走完整 4 级自动化流程
- **跨团队依赖联动 (F43)**：任务完成后调用 CrossTeamEngine.on_task_completed 解除下游阻塞
- **审批过期定时清理**：Dream Scheduler 每 30 分钟调用 ApprovalGateway.expire_stale()

### Fixed（修复）
- AgentLoop `_invoke_sub_agent` ToolResult 缺失 `call_id`/`tool_name` 字段
- ContextPayload `memories` 类型注解从 `dict` 修正为 `list[dict]`

## [10.1.0] - 2026-04-08

### Changed（变更）
- **全站界面中文化（27 个 Jinja 过滤器）**：所有后台页面的筛选项、状态徽章、等级标签统一显示中文
  - `ui_labels.py` 新增映射：`MODEL_PROVIDER`、`MODEL_ENABLED`、`CHANNEL`、`RESOURCE_TYPE`（39 种资源类型）、`HOOK_EVENT_TYPE`（53 种事件）、`KPI_GRADE`（A-D 四级）、`USER_TIER`（T1/T2/T3）
  - 模型管理页：提供商中文化、启用/停用中文标签、API 密钥中文标签
  - 用量统计页：表头 Token 列中文化（提示 Token / 生成 Token / 合计）、预算告警中文化
  - 上报时间线：Boss/Manager/Employee → 老板级/经理级/员工级
  - 记忆详情：层级徽章中文化（L1-L5）、审计信息层级中文化
  - KPI 评分页：等级选项中文化（优秀/良好/待改进/不合格）、周期标签中文化
  - 任务详情：评分等级中文化、评分下拉选项中文化
  - 总览页：审计日志 resource_type 中文化
  - 团队详情：机器人 channel 中文化（飞书/企业微信）
  - 员工工作台：申诉类型选项中文化、KPI 等级中文化
  - KPI partial / my_kpi：等级、负责角色中文化
  - 争议详情：目标对象类型中文化
  - 设置向导第 7 步：自动化档案中文化
  - 知识库待审页：Dream → 梦境引擎
  - 侧边栏用户足部：T1/T2/T3 → 管理员/经理/员工
  - base.html 用户 tier 显示中文化

## [10.0.0] - 2026-04-08

### Added（新增）
- **Agent 真实调用 LLM**：AgentLoop 通过 litellm + DeepSeek API 进行实际对话，包含完整 9 状态机、上下文加载、工具调用
- **`POST /api/chat` 接口**：HTTP JSON 方式调用 Agent（`{"team_id","message"}`），返回 AI 回复
- **WebSocket `/ws/chat`**：Dashboard 实时对话，流式分块回传，智能面板联动
- **自动化引擎**：
  - `check_overdue_tasks()` — 每 30 分钟检测超期任务，自动升级到员工/经理/老板
  - `auto_score_system_kpis()` — 每日 23:00 自动评分系统类 KPI（完成率、日报提交率）
  - `detect_anomalies()` — 每日 09:00 异常检测（3天无反馈、严重超期），自动创建审批请求
- **Dream Engine 激活**：
  - 记忆蒸馏用 LLM 总结对话关键信息（每日 02:00）
  - 知识提取从高质量反馈和已审核决策中提取（每日 03:00）
  - 日/周/月报告用 LLM 生成自然语言摘要
  - 报告自动推送到飞书/企微（`app/dream/push.py`）
- **飞书完整对接**：
  - 签名验证（`FEISHU_ENCRYPT_KEY` 配置后启用）
  - 消息接收 → Agent 处理 → 自动回复同 chat
  - 审批交互卡片（`build_approval_card`），老板在飞书点击批准/驳回
  - 卡片回调处理 + PATCH 更新卡片为结果态
- **`ModelRouter.get_model_with_key()`** / **`decrypt_api_key_for_model()`**：解密并传递 API Key
- **Dream Scheduler 9 个定时任务**：蒸馏、知识提取、日报、周报、月报、催办、KPI 评分、异常检测、留存预警
- **EventBus 分派循环启动**：事件驱动通知真正工作
- **NotificationService 启动**：实时推送通知

### Changed（变更）
- **`LLMClient`**：`deepseek-*` 自动映射为 litellm `deepseek/{name}` 格式
- **`AgentLoop`**：使用 `get_model_with_key` 传递 `api_key` 到 LLM 调用
- **安全配置**：`QFBJ_ENCRYPT_KEY` 固定默认值（不再每次重启随机生成），`SECRET_KEY` 可通过环境变量配置
- **`main.py` 生命周期**：正确接线 EventBus.start()、NotificationService.start()、setup_dream_scheduler()
- **Version**: 10.0.0

### Fixed（修复）
- `handle_inbound` 正确传递 `team` dict 和 `employee` dict 到 `AgentLoop.run()`
- 飞书 `_get_tenant_access_token` 改为异步（`httpx.AsyncClient`）
- T2 中间件放行 `/api` 前缀

## [Unreleased]

## [10.0.0] - 2026-04-08

### Fixed（修复）
- **核心生命周期接线**：入站 `handle_inbound` 按 `AgentLoop.run(message, team=…, employee=…, conversation_id=…)` 加载团队/员工字典并传入；`EventBus.start()` 启动分发循环；`NotificationService.start()` 订阅事件并启动合并刷新任务；Dream 在 `start_scheduler()` 前调用 `setup_dream_scheduler()` 注册定时任务
- **安全默认值**：`QFBJ_ENCRYPT_KEY` 未设置时使用固定默认字符串；`security` 对非 Fernet 格式密钥做 SHA256 派生，避免进程间随机密钥导致密文无法解密；仪表盘 `SECRET_KEY` 支持环境变量 `QFBJ_SECRET_KEY`

### Changed（变更）
- 应用版本号与健康检查返回版本统一为 **10.0.0**

## [9.0.0] - 2026-04-08

### Added（新增）
- **T2 数据隔离**：经理只能看到和操作自己团队的数据，总览/任务/KPI/审批/员工/升级全部按 team_id 过滤
- **全局 Toast 通知**：操作成功后右下角绿色提示（批准/驳回/创建/更新等15+个场景）
- **审批批量操作**：批量批准/批量驳回，含复选框和操作条
- **审批关联跳转**：详情页展示关联团队和员工的超链接，detail_json 渲染为键值表
- **KPI 评分历史页**：`/kpi/scores` — 录入评分、按团队/员工/周期筛选、等级色标
- **薪酬计算页**：`/salary` — 按团队+月份触发计算、匹配奖惩规则、展示结果表
- **文件上传**：知识库文件上传（`/knowledge/upload`）、任务反馈附件（`/tasks/{id}/feedback-file`），支持 Excel/CSV/PDF/图片等
- **员工自助门户(T3)**：`/my` — 我的任务、我的KPI、提交申诉、标记任务完成
- **辅导记录**：经理可给员工添加辅导笔记（`/employees/{id}/coaching`），含标签系统
- **日报模板**：团队可配置日报/周报/月报模板（`/teams/{id}/report-template`）
- **向导 UX 优化**：7步进度条、步骤标题、跳过按钮、完成动效和系统跳转

### Changed（变更）
- **总览页全面重做**：6大统计卡片（活跃团队/进行中任务/待审批/目标达成率/完成率/超期）、团队绩效表、快速审批、超期预警、最近动态、Token消耗
- 新增数据库迁移 `003_coaching.sql`（coaching_records + report_templates 表）
- 导航栏新增：薪酬计算入口
- Dashboard：`GET /salary`、`POST /salary/calculate` 薪酬计算页（规则对照、按团队周期批量计算）；侧栏「薪酬计算」与 `dollar-sign` 图标
- 审批中心：待办多选 + Alpine.js 批量操作条；`POST /approvals/batch-approve`、`POST /approvals/batch-reject`
- 审批详情：解析 `detail_json` 为键值展示；`team_id` 与 `detail_json` 中 `employee` 姓名匹配员工表后可点击跳转
- 本地上传模块 `app/core/uploads.py`（类型/大小校验，保存至 `data/uploads/`）；挂载 `GET /uploads` 静态目录
- `POST /knowledge/upload`：multipart 上传文件入库为知识（Excel/CSV 前几行摘要 + 下载路径）；知识库页「上传文件」表单
- `POST /tasks/{id}/feedback-file`：任务附件反馈（`feedback_type=file`）；任务详情附件表单与反馈列表下载链接；Jinja `basename` 过滤器

## [8.0.0] - 2026-04-08

### Added（新增）
- 完整 CRUD：任务状态变更/评分/反馈/删除（POST /tasks/{id}/status、feedback、score、delete）
- 完整 CRUD：KPI 编辑/删除（POST /kpi/{id}/update、delete）
- 完整 CRUD：知识库编辑/删除/审核通过/拒绝（POST /knowledge/{id}/update、delete、approve、reject）
- 完整 CRUD：模型编辑/删除/启停切换（POST /models/{id}/update、delete、toggle）
- 完整 CRUD：快捷指令删除（POST /commands/{id}/delete）
- 员工管理独立页面：列表/创建/编辑/删除，团队和角色筛选
- 团队发布：POST /teams/{id}/publish 设为 active 状态
- 升级处理：POST /escalations/{id}/respond 标记已响应
- Setup Wizard 无需登录即可访问（/wizard 加入白名单）

### Fixed（修复）
- 团队「发布」确认框发送空 body 无效 → 改为独立 POST /teams/{id}/publish
- 所有 POST 操作均真实写入数据库并 302 重定向

### Changed（变更）
- 导航栏新增「员工管理」入口
- 15 个页面全部 200 状态验证通过
- 所有 CRUD 操作通过 curl 端到端验证

## [7.5.0] - 2026-04-08

### Added（新增）
- 千帆海公司完整测试数据：6个Agent团队、19名员工、12条任务、10项KPI、3条审批、3个客户、5篇知识库、3个目标、4条奖惩规则、8个子Agent、2个LLM模型
- 种子数据脚本 `scripts/seed_data.py`，支持幂等执行
- 完整使用教程文档 `docs/使用教程.md`（15个章节，含5个日常管理场景示例）
- 完整测试用例文档 `docs/测试用例.md`（15大类、40+测试用例、自动化验证命令）

## [7.4.0] - 2026-04-08

### Fixed
- **BUG-ENUM-1**: 所有 Dashboard 模块写入数据库时 enum 对象改为 `.value`（auth.py, knowledge.py, wizard.py, approval.py, dispute.py, tasks.py, team_registry.py 共 12 处）
- **BUG-STATS-1**: `overview.py` 今日异常计数改为仅统计当天 escalations（原先统计全部历史）
- **BUG-STATS-2**: `approval.py` 详情页 stats 从数据库实际计算（原先全为零值占位）
- **BUG-STATS-3**: `dispute.py` 详情页 stats 从数据库实际计算（原先全为零值占位）
- **BUG-DISPUTE-1**: `dispute.py` 详情页补充员工姓名富化循环（与列表页保持一致）
- **BUG-TASK-1**: `tasks.py` 手动创建任务补充 `created_at` 字段
- **BUG-REPORTER-1**: `reporter.py` `_get_anomalies()` 改为按截止日期+未完成状态检测逾期（原先依赖 `status=overdue` 但任务状态机不含该过渡态）
- **BUG-KPI-1**: `kpi.py` `_calc_task_completion_rate()` 加入 `period_key` 日期过滤（原先忽略周期参数，统计全部任务）

## [7.3.0] - 2026-04-08

### Fixed
- **BUG-SAFETY-1**: Safety 层 EventBus 桩函数 — `approval.py`、`shadow.py`、`dispute.py` 中 `_publish()` 原先仅打日志，现已接入真实 EventBus 实例
- **BUG-SAFETY-2**: `calc_engine.py` 移除 `simpleeval` 缺失时的 `eval()` fallback，改为抛出 RuntimeError
- **BUG-SAFETY-3**: `hooks.py` 移除 `simpleeval` 缺失时的 `eval()` fallback，改为抛出 RuntimeError
- **BUG-SAFETY-4**: `sqlite_data.py` SQL 注入漏洞 — 新增列名正则校验，query 和 count 均已加固
- **BUG-SAFETY-5**: `file_parser.py` 路径遍历漏洞 — 新增 `ALLOWED_ROOTS` 白名单和 `_validate_path()` 校验
- **BUG-CORE-1**: `team_registry.py` 删除团队时 `team_shadow_config` 误将 team_id 当作记录 id 删除，改为按 team_id 字段 DELETE
- **BUG-CORE-2**: `database.py` 的 `insert()` 和 `update()` 方法会修改调用方传入的 dict，现在先复制一份
- **BUG-CORE-3**: `database.py` 的 `count()` 方法缺少对 list 值的 `IN (?)` 处理，已与 `query()` 保持一致
- **BUG-DREAM-1**: `extractor.py` 中错误的表名 `knowledges` 已全部修正为 `knowledge`
- **BUG-DATETIME**: Safety 层三个模块中所有 `datetime.utcnow()` 替换为 `datetime.now(timezone.utc)`

## [7.2.0] - 2026-04-08

### Fixed
- **BUG-01** `ContextLoader` → `ContextManager` 类名重命名，修复 agent_loop / sub_agent / __init__ 导入报错
- **BUG-02** 新增 `ContextPayload` dataclass，为上下文载荷提供类型安全结构
- **BUG-03** `ContextManager.load()` 签名改为接收 `team: dict` / `employee: dict` / `current_plan_summary` / `extra_variables`，与 AgentLoop 调用方对齐
- **BUG-04** 新增 `ContextManager.to_messages(payload)` 方法，将 ContextPayload 转为 LLM 消息列表
- **BUG-05** `ModelRouter` 新增 `select_cheap_model()` 方法，供压缩模块选取最低成本模型
- **BUG-07** `agent_loop.py` `user_tier` 由 `employee.tier`（不存在）改为基于 `employee.role` 的映射（boss→T1, manager→T2, employee→T3）
- **BUG-08** `_resolve_permission()` 新增 `_sub_agent_permission` 上限约束，确保子代理权限 ≤ 父级
- **BUG-09** `context.py` 压缩流程改为 `ModelRouter.get_instance()` 单例，避免重复实例化

## [7.1.0] - 2026-04-08

### Fixed
- 修复 Starlette 1.0 `TemplateResponse` API 兼容性（全部 37 处调用迁移到 `render()` 函数）
- 修复 `group.items` Jinja2 dict 方法冲突（重命名为 `group.links`）
- 修复 Dashboard 路由注册时序（middleware 必须在 app 创建时注册，不能在 lifespan 期间）
- 添加 `/health` 到公共路径白名单

### Added
- **服务器部署完成** — systemd 服务管理，自动重启
- `scripts/init_db.py` — 数据库初始化脚本（37 张表 + 默认管理员用户）
- `scripts/start.sh` — 快速启动脚本
- `render()` 辅助函数 — 统一 Starlette 1.0 模板渲染

### Changed
- `app/main.py` 重构 — 路由和中间件在 `create_app()` 注册（非 lifespan），避免 "Cannot add middleware after startup"
- 部署方式由 Docker 改为直接 pip + systemd（服务器网络环境限制）

## [7.0.0] - 2026-04-08

### Added
- **Package 6: Dashboard + Scenario Apps** — 完整 Web 管理后台，4 个核心模块 + 11 个 API 路由 + 30+ 模板
- **F36: Dashboard Framework** (`app/dashboard/app.py`) — FastAPI 路由注册、Jinja2 模板引擎、5 级侧边栏导航（总览/团队/任务与审批/规则与知识/系统与审计）、全局上下文注入
- **F36: Authentication** (`app/dashboard/auth.py`) — bcrypt 密码哈希、itsdangerous 签名 Cookie 会话（7 天）、T1 全权限 / T2 受限 / T3 禁止访问中间件、首次运行自动创建 admin/admin123
- **F36: Setup Wizard** (`app/dashboard/wizard.py`) — 7 步引导配置：欢迎→模型→组织模板→团队→员工→机器人→完成
- **F38: WebSocket Chat** (`app/dashboard/ws.py`) — WebSocket 实时聊天 + 智能面板（上下文实体检测→自动数据展示）
- P01-P12 全部 12 个页面路由及 30+ Jinja2 模板（含 HTMX 局部片段）
- 所有模板遵循 4 层页面结构：Header → 状态摘要卡片 → 主工作区 → 补充信息
- 统计卡片全部可点击跳转至目标页面
- 空状态包含三要素：原因说明 + 操作指引 + 行动按钮
- 危险操作（删除团队/删除记忆）均需确认弹窗
- 配置页面右侧固定操作栏（保存/发布/回滚）

### Changed
- 重写全部 Dashboard 模板为完整 HTML（TailwindCSS + Alpine.js + HTMX + ECharts CDN）

## [6.1.0] - 2026-04-08

### Added
- `data/migrations/002_commands.sql` — 快捷指令表迁移

### Fixed
- 修复 `tasks.py` 中 `task_feedback` 表名应为 `task_feedbacks`

## [6.0.0] - 2026-04-08

### Added
- **Package 2: Agent Runtime** — 完整 Agent 执行管线，6 个模块，全部生产级实现
- **F06: Agent Loop** (`app/runtime/agent_loop.py`) — 9 状态机（IDLE→RECEIVING_INPUT→COMMAND_ROUTING/LOADING_CONTEXT→THINKING→CALLING_TOOL→OBSERVING_RESULT→RESPONDING→IDLE, ERROR_HANDLING），最大 15 轮（可按团队 escalation_json.max_agent_turns 配置），`/` 命令直通技能路由绕过 LLM，每次工具结果后更新 `{current_plan_summary}`，per-employee asyncio.Lock 串行处理，自动对话记录持久化
- **F07: Context Manager** (`app/runtime/context.py`) — 7 维上下文加载（identity/employee/history/memories/knowledge/team_status/goals），80% token 阈值自动压缩（使用 gpt-4o-mini），压缩后验证"当前目标"和"未完成步骤"关键词保留，保留最近 5 轮完整对话，验证失败时带强调重新压缩
- **F08: LLM Client** (`app/runtime/llm.py`) — litellm 统一调用接口，支持 streaming/non-streaming，自动指数退避重试（3 次），token_counter 自动计数，LLMResponse 标准化包装（已有）
- **F09: Model Router** (`app/runtime/model_router.py`) — 按团队配置选择模型（primary→fallback→gpt-4o-mini），每日 token 用量追踪 upsert（model×team×day），80/90/95% 预算告警通过 EventBus 发送，超预算自动降级 + fallback 事件，按日去重告警避免重复
- **F10: Sub-Agent Runner** (`app/runtime/sub_agent.py`) — 4 标准角色（Director P4 / Analyst P0 只读 / Coach P0 建议 / Executor P2, P3+ 需审批），每个子代理独立 AgentLoop 实例，权限隔离 effective=min(parent, role_cap, db_cap)，便捷方法 invoke_analyst/invoke_coach/invoke_executor
- **F11: Prompt Engine** (`app/runtime/prompt_engine.py`) — 系统提示词 `{variable}` 插值，支持 dotted path（`{employee.name}`），缺失变量整段跳过，build_variables() 组装标准变量字典（扁平+嵌套双模式）
- `app/runtime/__init__.py` — 包导出（AgentLoop, ContextManager, LLMClient, LLMResponse, LoopSession, ModelRouter, PromptEngine, SubAgentRunner, SubAgentSpec）
- README.md Runtime API 文档更新至匹配实际实现

## [5.0.0] - 2026-04-08

### Added
- **Package 5: Core Business Engines** — 全部 14 个引擎模块
- **EngineBase** (`app/engines/base.py`) — 引擎基类，封装 DB 读写 + 审计日志，禁止直接 SQL
- **F17: Task Engine** (`app/engines/task.py`) — 任务全生命周期：创建→分派→反馈→三维评分（及时性40%+质量40%+复杂度20%）→完成
- **F18: KPI Engine** (`app/engines/kpi.py`) — KPI 定义（含数据源映射6字段）、加权评分、改进建议生成
- **F19: Goal Engine** (`app/engines/goal.py`) — 目标管理：级联分解、进度追踪、自动达成检测、父目标汇总
- **F20: Escalation Engine** (`app/engines/escalation.py`) — 三级升级（员工30min→经理60min→老板120min），间隔可配置，L3 自动提交审批
- **F21: Calc Engine** (`app/engines/calc.py`) — simpleeval 安全公式求值 + KPI-奖金联动计算
- **F32: Memory Distiller** (`app/dream/distiller.py`) — 每日对话蒸馏压缩为 L5 记忆，7 日留存自动清理
- **F33: Knowledge Extractor** (`app/dream/extractor.py`) — 从高分任务/A 级 KPI 中提取知识候选条目
- **F34: Report Generator** (`app/dream/reporter.py`) — 自动生成日报/周报/月报（含审批、异常、任务、风险、KPI 统计）
- **F35: Template Engine** (`app/dream/templates.py`) — 内置 9 套通知/报告模板，支持自定义扩展
- **Dream Scheduler** (`app/dream/scheduler.py`) — APScheduler 3.x 定时编排：蒸馏2AM、报告6AM、升级每10min、留存9AM
- **F40: Hiring Module** (`app/engines/hiring.py`) — 招聘画像（TOP30%自动推导）、JD 生成、面试模板、候选人评分、入职计划
- **F41: Decision Logger** (`app/engines/decision.py`) — 决策记录、指标快照、前后对比、月度复盘报告
- **F42: Customer Memory** (`app/engines/customer.py`) — 客户管理、联系记录、反馈、转移（保留历史）、30天流失预警
- **F43: Cross-Team Dependencies** (`app/engines/cross_team.py`) — 跨团队任务依赖、阻塞检测、完成自动解锁、瓶颈报告
- 所有 `__init__.py` 包导出文件
- README.md 更新功能列表、项目结构、API 文档

## [3.8.0] - 2026-04-08

### Added
- **F44: Approval Gateway** (`app/safety/approval.py`) — 4 级自动化审批网关（L1 通知 / L2 待审批 / L3 自动执行+汇报 / L4 静默执行），支持置信度降级（C+L3→L2, C+L4→L3）、超时过期、按团队 profile 自动匹配审批级别
- **F45: Shadow Mode** (`app/safety/shadow.py`) — 影子模式服务，所有 AI 动作可在干跑模式下记录而不产生副作用，支持启动/切换到线上、生成准确率分析报告
- **F46: Dispute Center** (`app/safety/dispute.py`) — 员工申诉中心，支持提交申诉、追加证据、裁决/推翻、AI 建议规则修正，自动快照被申诉对象的原始数据和 AI 推理链
- Safety Layer 包导出 (`app/safety/__init__.py`)
- 项目 README.md 和 CHANGELOG.md

## [3.0.0] - 2026-04-08

### Added
- **Package 3: System Infrastructure** — 技能系统、渠道系统、基础设施共 21 个模块

#### Sub-package 3.1: Skill System (`app/skills/`)
- **F12: Skill SDK** (`app/skills/sdk.py`) — `@tool` 装饰器、`ToolCall`/`ToolResult`/`ToolContext` 合约、自动 P0-P4 权限检查、自动审计日志、工具命名 `{skill}__{func}`
- **F16: Skill Registry** (`app/skills/registry.py`) — 统一技能注册中心，支持 builtin/custom(SKILL.md)/MCP 三源，按 team_id 和 sub-agent 查询，全局技能 `is_global=True`
- **F14: SKILL.md Parser** (`app/skills/skill_md.py`) — 解析 SKILL.md 为 prompt-based 技能模板并注册
- **F15: MCP Client** (`app/skills/mcp_client.py`) — MCP 服务端工具发现（`tools/list`）和代理执行（`tools/call`）
- **F13: sqlite_data 数据网关** (`app/skills/builtin/sqlite_data.py`) — 运行时唯一数据访问路径，query/insert/update/delete/count 全部自动注入 DataScopeManager 行过滤，写操作 P2+ 门控
- **F13: knowledge** (`app/skills/builtin/knowledge.py`) — BM25 + jieba 分词的中文知识库搜索、上传、浏览
- **F13: file_parser** (`app/skills/builtin/file_parser.py`) — Excel(openpyxl)/Markdown/Text 文件解析为结构化数据
- **F13: calc_engine** (`app/skills/builtin/calc_engine.py`) — simpleeval 沙箱公式求值，支持单条和批量计算
- **F13: notification** (`app/skills/builtin/notification.py`) — 抽象通知路由 + 智能合并（important=立即，normal=5min 批量）
- **F13: feishu_im** (`app/skills/builtin/feishu_im.py`) — 飞书消息/卡片/文件发送
- **F13: wecom_im** (`app/skills/builtin/wecom_im.py`) — 企业微信消息/卡片发送

#### Sub-package 3.2: Channels (`app/channels/`)
- **F22: Router** (`app/channels/router.py`) — 统一入站消息路由，平台消息→UnifiedMessage 转换，bot_id→team_id 映射
- **F23: Feishu** (`app/channels/feishu.py`) — 飞书 webhook 处理：URL challenge、签名验证、事件去重、消息解析
- **F24: WeCom** (`app/channels/wecom.py`) — 企业微信 WebSocket 长连接，指数退避自动重连，消息解析
- **F25: Bot Manager** (`app/channels/bot_manager.py`) — Bot 凭证 Fernet 加密存储、热重载（不重启生效）、连接测试、bot_id→team_id 路由表
- **F26: Notification Service** (`app/channels/notification.py`) — 事件驱动通知：重要事件立即发送，普通事件 5 分钟窗口合并

#### Sub-package 3.3: Infrastructure (`app/infra/`)
- **F28: Permission** (`app/infra/permission.py`) — T1/T2/T3 层级检查、P0-P4 操作级别检查、Dashboard 节段访问控制、FastAPI 中间件
- **F27: Memory** (`app/infra/memory.py`) — 5 层记忆系统 (L1 系统规则→L5 对话摘要)、9 场景 × 5 层调度表、可审计元数据（source/created_by/reference_count/is_verified）
- **F29: EventBus** (`app/infra/eventbus.py`) — asyncio.Queue pub/sub、精确/前缀/通配符订阅、关键事件自动持久化到 audit_logs
- **F30: Hook Engine** (`app/infra/hooks.py`) — 事件→simpleeval 条件→动作管线、仪表盘可配置规则、6 种内置动作类型
- **F31: Audit Writer** (`app/infra/audit.py`) — 非阻塞缓冲 + 定时 flush 批量写入、1 年留存策略清理助手
