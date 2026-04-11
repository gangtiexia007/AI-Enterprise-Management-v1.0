from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


# ---------- Employee ----------

class EmployeeBase(BaseModel):
    name: str
    department: str = ""
    position: str = ""
    feishu_id: str = ""

class EmployeeCreate(EmployeeBase): pass

class EmployeeOut(EmployeeBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Goal ----------

class GoalBase(BaseModel):
    title: str
    parent_id: Optional[int] = None
    level: str = "company"
    owner: str = ""
    target_value: float = 0
    current_value: float = 0
    unit: str = ""
    deadline: Optional[date] = None
    status: str = "active"

class GoalCreate(GoalBase): pass
class GoalUpdate(BaseModel):
    title: Optional[str] = None
    owner: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    deadline: Optional[date] = None
    status: Optional[str] = None

class GoalOut(GoalBase):
    id: int
    created_at: datetime
    children: List[GoalOut] = []
    progress: float = 0
    class Config:
        from_attributes = True


# ---------- Task ----------

class TaskBase(BaseModel):
    title: str
    description: str = ""
    assignee_id: Optional[int] = None
    assignee_name: str = ""
    deadline: Optional[date] = None
    goal_id: Optional[int] = None
    priority: str = "normal"
    task_type: str = ""
    parent_task_id: Optional[int] = None
    auto_next_config: str = ""

class TaskCreate(TaskBase): pass
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    task_type: Optional[str] = None
    auto_next_config: Optional[str] = None

class TaskOut(TaskBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


TASK_TEMPLATES = {
    "赛道研究": {
        "task_type": "赛道研究",
        "description": "选品研究：发掘并拆分细分赛道，输出可执行的赛道方向+文案清单",
        "priority": "high",
        "deadline_offset_days": 3,
        "auto_next_config": '{"next_type":"铺货上架","assignee_department":"铺货组","deadline_offset_hours":72,"title_template":"铺货：{context} 首批上架","description_template":"按矩阵铺货流程完成 {context} 的首批 20-50 款上架，上架后在款式跟踪表中录入记录。"}'
    },
    "铺货上架": {
        "task_type": "铺货上架",
        "description": "按矩阵展开出设计 → 写产品链接 → 上架到测试店，每日 10-15 款",
        "priority": "high",
        "deadline_offset_days": 3,
        "auto_next_config": '{"next_type":"数据检查","assignee_department":"优化组","deadline_offset_hours":72,"title_template":"数据检查：{context} 3日数据","description_template":"采集 {context} 上架后 3 天的曝光/点击数据，录入款式跟踪表，标记初步分级。"}'
    },
    "数据检查": {
        "task_type": "数据检查",
        "description": "采集各平台数据，更新款式跟踪表，按筛选规则标记 S/A/B/C 分级",
        "priority": "normal",
        "deadline_offset_days": 3,
        "auto_next_config": ""
    },
    "变体制作": {
        "task_type": "变体制作",
        "description": "为 S 级爆款制作 5-10 个变体（换文案/配色/字体/排版），移入垂直店",
        "priority": "high",
        "deadline_offset_days": 2,
        "auto_next_config": ""
    },
    "产品优化": {
        "task_type": "产品优化",
        "description": "对 B 类款式进行优化：换主图/改标题标签/调价格，一次只改一个变量",
        "priority": "normal",
        "deadline_offset_days": 2,
        "auto_next_config": ""
    },
    "跨平台分发": {
        "task_type": "跨平台分发",
        "description": "将已验证的设计同步到其他平台（TikTok↔Shopee↔Temu），适配各平台规则",
        "priority": "normal",
        "deadline_offset_days": 3,
        "auto_next_config": ""
    },
}


# ---------- Feedback ----------

class FeedbackCreate(BaseModel):
    task_id: Optional[int] = None
    employee_id: Optional[int] = None
    content: str = ""
    files: str = ""

class FeedbackOut(FeedbackCreate):
    id: int
    submitted_at: datetime
    class Config:
        from_attributes = True


# ---------- KPI ----------

class KPIBase(BaseModel):
    employee_id: int
    employee_name: str = ""
    metric_name: str
    target_value: float = 0
    actual_value: float = 0
    weight: float = 1.0
    period: str = ""

class KPICreate(KPIBase): pass
class KPIUpdate(BaseModel):
    actual_value: Optional[float] = None
    score: Optional[float] = None
    grade: Optional[str] = None
    ai_comment: Optional[str] = None

class KPIOut(KPIBase):
    id: int
    score: float
    grade: str
    ai_comment: str
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Knowledge ----------

class KnowledgeBase(BaseModel):
    category: str = "sop"
    title: str
    content: str = ""
    source: str = "manual"

class KnowledgeCreate(KnowledgeBase): pass
class KnowledgeUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None

class KnowledgeOut(KnowledgeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# ---------- Conversation ----------

class MessageIn(BaseModel):
    content: str

class ConversationOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Settings ----------

class SettingItem(BaseModel):
    key: str
    value: str

class SettingOut(SettingItem):
    id: int
    class Config:
        from_attributes = True


# ---------- Dashboard Stats ----------

class DashboardStats(BaseModel):
    total_tasks: int = 0
    overdue_tasks: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    in_progress_tasks: int = 0
    goal_progress: float = 0
    avg_kpi_score: float = 0
    knowledge_count: int = 0
    employee_count: int = 0
    pending_approvals: int = 0


# ---------- Escalation ----------

class EscalationOut(BaseModel):
    id: int
    task_id: int
    level: str
    message: str
    sent_at: datetime
    responded: int
    class Config:
        from_attributes = True


# ---------- Approval ----------

class ApprovalBase(BaseModel):
    type: str = "general"
    title: str
    detail: str = ""
    priority: int = 2

class ApprovalCreate(ApprovalBase): pass

class ApprovalOut(ApprovalBase):
    id: int
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: str = ""
    class Config:
        from_attributes = True


# ---------- Coaching ----------

class CoachingBase(BaseModel):
    employee_id: int
    type: str = "general"
    content: str = ""

class CoachingCreate(CoachingBase): pass

class CoachingOut(CoachingBase):
    id: int
    ai_suggestion: str = ""
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Token Usage ----------

class TokenUsageOut(BaseModel):
    id: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    endpoint: str
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Audit Log ----------

class AuditLogOut(BaseModel):
    id: int
    action: str
    detail: str
    actor: str = "system"
    resource_type: str = ""
    resource_id: str = ""
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Agent Harness ----------

class AgentBase(BaseModel):
    name: str
    description: str = ""
    model_primary: str = "gpt-4o-mini"
    model_fallback: str = "gpt-3.5-turbo"
    system_prompt: str = ""
    mode: str = "full"
    max_tokens: int = 4000
    status: str = "active"

class AgentCreate(AgentBase): pass
class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_primary: Optional[str] = None
    model_fallback: Optional[str] = None
    system_prompt: Optional[str] = None
    mode: Optional[str] = None
    max_tokens: Optional[int] = None
    status: Optional[str] = None

class AgentOut(AgentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


class SkillBase(BaseModel):
    name: str
    type: str = "builtin"
    description: str = ""
    config: str = "{}"
    enabled: int = 1
    permission_level: int = 0

class SkillCreate(SkillBase): pass
class SkillUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    config: Optional[str] = None
    enabled: Optional[int] = None
    permission_level: Optional[int] = None

class SkillOut(SkillBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


class AgentSkillCreate(BaseModel):
    agent_id: int
    skill_id: int


# ---------- Scheduled Task ----------

class ScheduledTaskBase(BaseModel):
    name: str
    task_type: str
    cron_expression: str = ""
    enabled: int = 1
    config: str = "{}"

class ScheduledTaskCreate(ScheduledTaskBase): pass
class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    enabled: Optional[int] = None
    config: Optional[str] = None

class ScheduledTaskOut(ScheduledTaskBase):
    id: int
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Memory Entry ----------

class MemoryEntryOut(BaseModel):
    id: int
    level: int
    title: str
    content: str
    source_type: str
    confidence: float
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Token Budget ----------

class TokenBudgetOut(BaseModel):
    id: int
    period: str
    period_type: str
    budget_tokens: int
    used_tokens: int
    budget_cost: float
    used_cost: float
    alert_sent: int
    created_at: datetime
    class Config:
        from_attributes = True

class TokenBudgetUpdate(BaseModel):
    budget_tokens: Optional[int] = None
    budget_cost: Optional[float] = None


# ---------- Team ----------

class TeamBase(BaseModel):
    name: str
    description: str = ""
    leader_id: Optional[int] = None
    feishu_chat_id: str = ""

class TeamCreate(TeamBase): pass
class TeamOut(TeamBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True


# ---------- Bitable ----------

class BitableConfigOut(BaseModel):
    base_token: str = ""
    table_map: dict[str, str] = {}
    category_map: dict[str, str] = {}


class BitableConfigUpdate(BaseModel):
    base_token: Optional[str] = None
    table_map: Optional[dict[str, str]] = None
    category_map: Optional[dict[str, str]] = None


class BitableRecordOut(BaseModel):
    record_id: str
    fields: dict = {}


class BitableTableOverview(BaseModel):
    alias: str
    category: str  # A | B | C
    table_id: str = ""
    record_count: int = 0
    last_sync_at: Optional[str] = None


class BitableSyncResult(BaseModel):
    ok: bool
    alias: str = ""
    detail: str = ""
    invalidated_tables: list[str] = []


class BitableTableMetaOut(BaseModel):
    table_id: Optional[str] = None
    name: Optional[str] = None
    revision: Optional[int] = None


GoalOut.model_rebuild()
