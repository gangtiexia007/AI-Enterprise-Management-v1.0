"""Chinese display labels for dashboard filters and badges (DB values stay English)."""

from __future__ import annotations

# ── Maps: internal value → 中文展示 ─────────────────────────────────

TEAM_STATUS: dict[str, str] = {
    "draft": "草稿",
    "active": "运行中",
    "shadow": "影子模式",
    "live": "已上线",
    "disabled": "已停用",
}

TASK_STATUS: dict[str, str] = {
    "pending": "待处理",
    "dispatched": "已派发",
    "in_progress": "进行中",
    "submitted": "已提交",
    "scored": "已评分",
    "completed": "已完成",
    "overdue": "已逾期",
}

APPROVAL_STATUS: dict[str, str] = {
    "pending": "待审批",
    "approved": "已通过",
    "rejected": "已拒绝",
    "withdrawn": "已撤回",
    "expired": "已超时",
}

APPROVAL_TYPE: dict[str, str] = {
    "team_create": "团队创建",
    "task_dispatch": "任务派发",
    "kpi_score": "KPI 评分",
    "reward_calc": "薪酬/奖金计算",
    "goal_split": "目标拆解",
    "knowledge_candidate": "知识候选",
    "risk_alert": "风险预警",
    "escalation_boss": "升级至老板",
    "cross_team_trigger": "跨团队触发",
    "coaching_suggestion": "辅导建议",
    "employee_transfer": "员工调动",
}

CONFIDENCE: dict[str, str] = {
    "A": "高 (A)",
    "B": "中 (B)",
    "C": "低 (C)",
}

DISPUTE_STATUS: dict[str, str] = {
    "filed": "已提交",
    "evidence_collected": "举证中",
    "ruling": "裁决中",
    "resolved": "已解决",
    "overturned": "已推翻",
}

DISPUTE_TYPE: dict[str, str] = {
    "kpi_score": "KPI 分数",
    "task_quality": "任务质量",
    "reward": "奖惩",
    "risk_label": "风险标签",
}

ESCALATION_LEVEL: dict[str, str] = {
    "employee": "员工级",
    "manager": "经理级",
    "boss": "老板级",
}

EMPLOYEE_ROLE: dict[str, str] = {
    "boss": "老板",
    "manager": "经理",
    "employee": "员工",
}

EMPLOYEE_STATUS: dict[str, str] = {
    "active": "在职",
    "transferring": "调动中",
    "resigned": "已离职",
}

REWARD_STATUS: dict[str, str] = {
    "calculated": "已计算",
    "pending_approval": "待审批",
    "approved": "已批准",
    "paid": "已发放",
}

AUTOMATION_PROFILE: dict[str, str] = {
    "startup": "创业团队",
    "mid_manager": "中层管理型",
    "process_driven": "流程驱动型",
}

KNOWLEDGE_SCOPE: dict[str, str] = {
    "company": "公司级",
    "department": "部门级",
}

KNOWLEDGE_STATUS: dict[str, str] = {
    "active": "已发布",
    "candidate": "候选",
    "archived": "已归档",
}

MEMORY_LAYER: dict[str, str] = {
    "L1": "L1 系统规则",
    "L2": "L2 团队 SOP",
    "L3": "L3 员工画像",
    "L4": "L4 业务知识",
    "L5": "L5 对话摘要",
}

KPI_PERIOD: dict[str, str] = {
    "daily": "日",
    "weekly": "周",
    "monthly": "月",
}

SUB_AGENT_ROLE: dict[str, str] = {
    "director": "总控",
    "analyst": "分析",
    "coach": "辅导",
    "executor": "执行",
}

AUTOMATION_LEVEL: dict[str, str] = {
    "L1": "L1 仅提醒",
    "L2": "L2 建议待批",
    "L3": "L3 自动执行并报告",
    "L4": "L4 全自动",
}

KPI_SOURCE_TYPE: dict[str, str] = {
    "manual": "手工录入",
    "system": "系统计算",
    "external": "外部系统",
}

FEEDBACK_TYPE: dict[str, str] = {
    "text": "文字",
    "file": "附件",
}

MODEL_PROVIDER: dict[str, str] = {
    "openai": "OpenAI",
    "deepseek": "DeepSeek",
    "anthropic": "Anthropic",
    "zhipu": "智谱",
    "moonshot": "Moonshot",
    "other": "其他",
}

MODEL_ENABLED: dict[str, str] = {
    "True": "启用",
    "true": "启用",
    "1": "启用",
    "False": "停用",
    "false": "停用",
    "0": "停用",
}

CHANNEL: dict[str, str] = {
    "feishu": "飞书",
    "wecom": "企业微信",
    "dashboard": "管理后台",
}

RESOURCE_TYPE: dict[str, str] = {
    "team": "团队",
    "teams": "团队",
    "employee": "员工",
    "employees": "员工",
    "task": "任务",
    "tasks": "任务",
    "kpi": "KPI",
    "kpi_definitions": "KPI 定义",
    "kpi_scores": "KPI 评分",
    "approval": "审批",
    "approval_requests": "审批请求",
    "dispute": "争议",
    "disputes": "争议",
    "knowledge": "知识",
    "knowledge_base": "知识库",
    "memory": "记忆",
    "memories": "记忆",
    "model": "模型",
    "models": "模型",
    "goal": "目标",
    "goals": "目标",
    "reward": "薪酬",
    "salary_records": "薪酬记录",
    "escalation": "上报",
    "escalations": "上报",
    "customer": "客户",
    "customers": "客户",
    "decision": "决策",
    "decision_logs": "决策日志",
    "skill": "技能",
    "skills": "技能",
    "command": "指令",
    "commands": "指令",
    "report": "报告",
    "dream_reports": "梦境报告",
    "report_templates": "报告模板",
    "bot": "机器人",
    "team_bots": "团队机器人",
    "sub_agent": "子智能体",
    "sub_agents": "子智能体",
    "hook": "Hook 规则",
    "hooks": "Hook 规则",
    "user": "用户",
    "users": "用户",
}

HOOK_EVENT_TYPE: dict[str, str] = {
    "team.created": "团队创建",
    "team.updated": "团队更新",
    "team.disabled": "团队停用",
    "team.shadow_started": "影子模式启动",
    "team.switched_live": "团队上线",
    "employee.joined": "员工加入",
    "employee.transferred": "员工调动",
    "employee.resigned": "员工离职",
    "employee.birthday": "员工生日",
    "employee.contract_expiring": "合同即将到期",
    "task.created": "任务创建",
    "task.dispatched": "任务派发",
    "task.submitted": "任务提交",
    "task.scored": "任务评分",
    "task.completed": "任务完成",
    "task.overdue": "任务逾期",
    "kpi.scored": "KPI 评分",
    "kpi.approved": "KPI 审批通过",
    "kpi.disputed": "KPI 申诉",
    "goal.created": "目标创建",
    "goal.progress_updated": "目标进度更新",
    "goal.achieved": "目标达成",
    "goal.failed": "目标未达成",
    "escalation.level1": "一级上报",
    "escalation.level2": "二级上报",
    "escalation.level3": "三级上报",
    "approval.submitted": "审批提交",
    "approval.approved": "审批通过",
    "approval.rejected": "审批拒绝",
    "approval.expired": "审批超时",
    "approval.withdrawn": "审批撤回",
    "shadow.started": "影子模式启动",
    "shadow.report_generated": "影子报告生成",
    "shadow.switched_live": "影子模式切换上线",
    "dispute.filed": "争议提交",
    "dispute.resolved": "争议解决",
    "dispute.overturned": "争议推翻",
    "dream.distill_completed": "记忆蒸馏完成",
    "dream.knowledge_candidate": "知识候选生成",
    "dream.report_generated": "梦境报告生成",
    "reward.calculated": "薪酬计算完成",
    "reward.approved": "薪酬审批通过",
    "reward.paid": "薪酬发放",
    "customer.created": "客户创建",
    "customer.feedback": "客户反馈",
    "customer.churn_warning": "客户流失预警",
    "decision.recorded": "决策记录",
    "decision.tracked": "决策跟踪",
    "decision.reviewed": "决策复盘",
    "hiring.profile_created": "招聘画像创建",
    "hiring.candidate_scored": "候选人评分",
    "hiring.onboarding_started": "入职启动",
    "cross_team.upstream_completed": "上游任务完成",
    "cross_team.bottleneck_detected": "瓶颈检测",
    "notification.sent": "通知发送",
    "notification.merged": "通知合并",
    "model.budget_warning": "模型预算预警",
    "model.budget_exceeded": "模型预算超限",
    "model.fallback_triggered": "模型降级触发",
}

REVIEW_STATUS: dict[str, str] = {
    "pending": "待复盘",
    "reviewed": "已复盘",
    "skipped": "已跳过",
}

CANDIDATE_STATUS: dict[str, str] = {
    "pending": "待处理",
    "screening": "筛选中",
    "interview": "面试中",
    "scored": "已评分",
    "offered": "已发 Offer",
    "hired": "已入职",
    "rejected": "已拒绝",
}

KPI_GRADE: dict[str, str] = {
    "A": "优秀 (A)",
    "B": "良好 (B)",
    "C": "待改进 (C)",
    "D": "不合格 (D)",
}

USER_TIER: dict[str, str] = {
    "T1": "管理员",
    "T2": "经理",
    "T3": "员工",
}


def _lookup(mapping: dict[str, str], value: str | None) -> str:
    if value is None:
        return ""
    key = str(value).strip()
    return mapping.get(key, key)


def register_jinja_filters(env) -> None:
    """Register all zh_* filters on a Jinja2 Environment."""
    env.filters["zh_team_status"] = lambda v: _lookup(TEAM_STATUS, v)
    env.filters["zh_task_status"] = lambda v: _lookup(TASK_STATUS, v)
    env.filters["zh_approval_status"] = lambda v: _lookup(APPROVAL_STATUS, v)
    env.filters["zh_approval_type"] = lambda v: _lookup(APPROVAL_TYPE, v)
    env.filters["zh_confidence"] = lambda v: _lookup(CONFIDENCE, v)
    env.filters["zh_dispute_status"] = lambda v: _lookup(DISPUTE_STATUS, v)
    env.filters["zh_dispute_type"] = lambda v: _lookup(DISPUTE_TYPE, v)
    env.filters["zh_escalation_level"] = lambda v: _lookup(ESCALATION_LEVEL, v)
    env.filters["zh_employee_role"] = lambda v: _lookup(EMPLOYEE_ROLE, v)
    env.filters["zh_employee_status"] = lambda v: _lookup(EMPLOYEE_STATUS, v)
    env.filters["zh_reward_status"] = lambda v: _lookup(REWARD_STATUS, v)
    env.filters["zh_automation_profile"] = lambda v: _lookup(AUTOMATION_PROFILE, v)
    env.filters["zh_knowledge_scope"] = lambda v: _lookup(KNOWLEDGE_SCOPE, v)
    env.filters["zh_knowledge_status"] = lambda v: _lookup(KNOWLEDGE_STATUS, v)
    env.filters["zh_memory_layer"] = lambda v: _lookup(MEMORY_LAYER, v)
    env.filters["zh_kpi_period"] = lambda v: _lookup(KPI_PERIOD, v)
    env.filters["zh_sub_agent_role"] = lambda v: _lookup(SUB_AGENT_ROLE, v)
    env.filters["zh_automation_level"] = lambda v: _lookup(AUTOMATION_LEVEL, v)
    env.filters["zh_kpi_source_type"] = lambda v: _lookup(KPI_SOURCE_TYPE, v)
    env.filters["zh_feedback_type"] = lambda v: _lookup(FEEDBACK_TYPE, v)
    env.filters["zh_model_provider"] = lambda v: _lookup(MODEL_PROVIDER, v)
    env.filters["zh_model_enabled"] = lambda v: _lookup(MODEL_ENABLED, v)
    env.filters["zh_channel"] = lambda v: _lookup(CHANNEL, v)
    env.filters["zh_resource_type"] = lambda v: _lookup(RESOURCE_TYPE, v)
    env.filters["zh_hook_event_type"] = lambda v: _lookup(HOOK_EVENT_TYPE, v)
    env.filters["zh_kpi_grade"] = lambda v: _lookup(KPI_GRADE, v)
    env.filters["zh_user_tier"] = lambda v: _lookup(USER_TIER, v)
    env.filters["zh_review_status"] = lambda v: _lookup(REVIEW_STATUS, v)
    env.filters["zh_candidate_status"] = lambda v: _lookup(CANDIDATE_STATUS, v)
