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

class TaskCreate(TaskBase): pass
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class TaskOut(TaskBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


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


class SubAgentBase(BaseModel):
    parent_agent_id: Optional[int] = None
    role: str
    name: str
    description: str = ""
    model: str = ""
    allowed_tools: str = "[]"
    read_only: int = 1
    can_spawn_children: int = 0
    system_prompt: str = ""
    status: str = "active"

class SubAgentCreate(SubAgentBase): pass
class SubAgentUpdate(BaseModel):
    role: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    allowed_tools: Optional[str] = None
    read_only: Optional[int] = None
    can_spawn_children: Optional[int] = None
    system_prompt: Optional[str] = None
    status: Optional[str] = None

class SubAgentOut(SubAgentBase):
    id: int
    created_at: datetime
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


GoalOut.model_rebuild()
