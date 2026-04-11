from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Date, ForeignKey, Enum as SAEnum,
)
from database import Base
import enum


# ---------- Enums ----------

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    OVERDUE = "overdue"
    FEEDBACK_SUBMITTED = "feedback_submitted"
    DONE = "done"


class GoalLevel(str, enum.Enum):
    COMPANY = "company"
    DEPARTMENT = "department"
    INDIVIDUAL = "individual"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    OVERDUE = "overdue"


class KnowledgeCategory(str, enum.Enum):
    SOP = "sop"
    CASE = "case"
    RULE = "rule"
    TABOO = "taboo"


# ---------- Models ----------

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), default="")
    position = Column(String(100), default="")
    feishu_id = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    parent_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    level = Column(SAEnum(GoalLevel), default=GoalLevel.COMPANY)
    owner = Column(String(100), default="")
    target_value = Column(Float, default=0)
    current_value = Column(Float, default=0)
    unit = Column(String(50), default="")
    deadline = Column(Date, nullable=True)
    status = Column(SAEnum(GoalStatus), default=GoalStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    assignee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    assignee_name = Column(String(100), default="")
    deadline = Column(Date, nullable=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.PENDING)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    priority = Column(String(20), default="normal")
    task_type = Column(String(100), default="")
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    auto_next_config = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    content = Column(Text, default="")
    files = Column(Text, default="")
    submitted_at = Column(DateTime, default=datetime.utcnow)


class KPIRecord(Base):
    __tablename__ = "kpi_records"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    employee_name = Column(String(100), default="")
    metric_name = Column(String(200), nullable=False)
    target_value = Column(Float, default=0)
    actual_value = Column(Float, default=0)
    weight = Column(Float, default=1.0)
    score = Column(Float, default=0)
    grade = Column(String(10), default="")
    period = Column(String(50), default="")
    ai_comment = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class EscalationLog(Base):
    __tablename__ = "escalation_logs"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    level = Column(String(50), default="employee")
    message = Column(Text, default="")
    sent_at = Column(DateTime, default=datetime.utcnow)
    responded = Column(Integer, default=0)


class Knowledge(Base):
    __tablename__ = "knowledge"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(SAEnum(KnowledgeCategory), default=KnowledgeCategory.SOP)
    title = Column(String(300), nullable=False)
    content = Column(Text, default="")
    source = Column(String(200), default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # unified memory fields (merged from MemoryEntry + AgentMemoryEntry)
    level = Column(Integer, default=3)              # 2=摘要, 3=知识(默认), 4=蒸馏
    platform = Column(String(100), default="")
    market = Column(String(100), default="")
    niche = Column(String(200), default="")
    persona = Column(String(200), default="")
    confidence = Column(Float, default=1.0)
    source_run_id = Column(String(100), default="")
    memory_type = Column(String(50), default="")    # SOP/case/rule/taboo/risk_expression …
    conditions = Column(Text, default="[]")         # JSON
    action = Column(Text, default="")
    result = Column(Text, default="")
    why = Column(Text, default="")
    reusable = Column(Integer, default=1)
    metadata_json = Column(Text, default="{}")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(200), unique=True, nullable=False)
    value = Column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(200), nullable=False)
    detail = Column(Text, default="")
    actor = Column(String(100), default="system")
    resource_type = Column(String(100), default="")
    resource_id = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(100), default="general")
    title = Column(String(300), nullable=False)
    detail = Column(Text, default="")
    priority = Column(Integer, default=2)
    status = Column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), default="")


class CoachingRecord(Base):
    __tablename__ = "coaching_records"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    type = Column(String(100), default="general")
    content = Column(Text, default="")
    ai_suggestion = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class TokenUsage(Base):
    __tablename__ = "token_usage"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String(100), default="")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0)
    endpoint = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------- Agent Harness ----------

class AgentMode(str, enum.Enum):
    COMMAND = "command"
    LIGHT = "light"
    FULL = "full"


class SkillType(str, enum.Enum):
    BUILTIN = "builtin"
    CUSTOM = "custom"
    MCP = "mcp"


class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    model_primary = Column(String(200), default="gpt-4o-mini")
    model_fallback = Column(String(200), default="gpt-3.5-turbo")
    system_prompt = Column(Text, default="")
    mode = Column(SAEnum(AgentMode), default=AgentMode.FULL)
    max_tokens = Column(Integer, default=4000)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    type = Column(SAEnum(SkillType), default=SkillType.BUILTIN)
    description = Column(Text, default="")
    config = Column(Text, default="{}")
    enabled = Column(Integer, default=1)
    permission_level = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)


# ---------- Scheduled Tasks ----------

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    task_type = Column(String(100), nullable=False)  # daily_report, weekly_report, monthly_report, coaching, memory_distill, kpi_alert
    cron_expression = Column(String(100), default="")  # human-readable: "09:00", "每周一09:00" etc
    enabled = Column(Integer, default=1)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    config = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------- Memory Entries (L4 distilled) ----------
# DEPRECATED - use Knowledge table instead

class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    id = Column(Integer, primary_key=True, index=True)
    level = Column(Integer, default=4)  # 4=distilled patterns, 2=summaries
    title = Column(String(300), default="")
    content = Column(Text, default="")
    source_type = Column(String(100), default="conversation")  # conversation, task, feedback
    source_ids = Column(Text, default="")  # JSON list of source conversation IDs
    confidence = Column(Float, default=0.8)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------- Token Budget ----------

class TokenBudget(Base):
    __tablename__ = "token_budget"
    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(20), nullable=False)  # "2026-04", "2026-04-09"
    period_type = Column(String(10), default="monthly")  # daily / monthly
    budget_tokens = Column(Integer, default=0)
    used_tokens = Column(Integer, default=0)
    budget_cost = Column(Float, default=0)
    used_cost = Column(Float, default=0)
    alert_sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------- Teams ----------

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    leader_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    feishu_chat_id = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------- POD 3.0 Performance ----------

class PodOrder(Base):
    __tablename__ = "pod_orders"
    id = Column(Integer, primary_key=True)
    erp_order_id = Column(String(100), unique=True, index=True)
    platform_order_id = Column(String(100), default="")
    tracking_number = Column(String(100), default="")
    platform = Column(String(50), index=True, default="")
    country = Column(String(10), index=True, default="")
    store = Column(String(200), index=True, default="")
    operator = Column(String(50), index=True, default="")
    platform_product_id = Column(String(100), default="")
    platform_sku = Column(String(200), default="")
    product_spec = Column(String(300), default="")
    sku = Column(String(100), index=True, default="")
    pod_spec = Column(String(200), default="")
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0)
    discount_price = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    paid_amount = Column(Float, default=0)
    paid_amount_cny = Column(Float, default=0)
    currency = Column(String(10), default="PHP")
    payment_method = Column(String(50), default="")
    production_mode = Column(String(50), default="")
    order_tag = Column(String(100), default="")
    product_title = Column(String(500), default="")
    shipping_fee = Column(Float, default=0)
    order_status = Column(String(50), default="")
    status_category = Column(String(20), default="")
    failure_reason = Column(String(300), default="")
    niche = Column(String(100), index=True, default="")
    order_date = Column(Date, index=True)
    payment_time = Column(DateTime, nullable=True)
    expected_ship_time = Column(DateTime, nullable=True)
    arrange_time = Column(DateTime, nullable=True)
    created_time = Column(DateTime, nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow)


class PodProduct(Base):
    __tablename__ = "pod_products"
    id = Column(Integer, primary_key=True)
    erp_product_id = Column(String(100), index=True, default="")
    platform = Column(String(50), index=True, default="")
    product_name = Column(String(500), default="")
    platform_sku = Column(String(200), index=True, default="")
    price = Column(Float, default=0)
    store = Column(String(200), index=True, default="")
    operator = Column(String(50), index=True, default="")
    niche = Column(String(100), index=True, default="")
    upload_date = Column(Date, index=True)
    has_order = Column(Integer, default=0)
    first_order_date = Column(Date, nullable=True)
    total_orders = Column(Integer, default=0)
    imported_at = Column(DateTime, default=datetime.utcnow)


# ---------- Multi-Agent System ----------

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False)
    task_type = Column(String(100), default="")
    route_name = Column(String(100), default="")
    agents_called = Column(Text, default="[]")
    input_summary = Column(Text, default="")
    final_output = Column(Text, default="")
    total_tokens = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    data_sufficiency = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# DEPRECATED - use Knowledge table instead
class AgentMemoryEntry(Base):
    __tablename__ = "agent_memory_entries"
    id = Column(Integer, primary_key=True, index=True)
    memory_type = Column(String(50), default="")
    title = Column(String(300), default="")
    platform = Column(String(100), default="")
    market = Column(String(100), default="")
    persona = Column(String(200), default="")
    niche = Column(String(200), default="")
    conditions = Column(Text, default="[]")
    action = Column(Text, default="")
    result = Column(Text, default="")
    why = Column(Text, default="")
    reusable = Column(Integer, default=1)
    source_run_id = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
