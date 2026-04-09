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
