"""Global enums — state machines, permission levels, automation tiers.

All state transitions and classification values are defined here.
No module should invent its own status strings.
"""

from enum import Enum


# ── Permission & Governance ──────────────────────────────────────────

class UserTier(str, Enum):
    T1 = "T1"  # Boss – full access
    T2 = "T2"  # Manager – department scope
    T3 = "T3"  # Employee – IM + 员工自助工作台 /my（需绑定 employee_id）


class PermissionLevel(int, Enum):
    P0 = 0  # Read-only public data
    P1 = 1  # Read team data
    P2 = 2  # Write team data
    P3 = 3  # Sensitive operations (requires dashboard confirmation)
    P4 = 4  # Critical operations (requires approval gateway)


class AutomationLevel(str, Enum):
    L1 = "L1"  # Notify only
    L2 = "L2"  # Suggest & wait for approval
    L3 = "L3"  # Auto-execute & report
    L4 = "L4"  # Full auto, no interruption


class Confidence(str, Enum):
    A = "A"  # High – eligible for auto-execution
    B = "B"  # Medium – suggest approval
    C = "C"  # Low – auto-downgrade automation level


# ── Team & Employee ──────────────────────────────────────────────────

class TeamStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SHADOW = "shadow"
    LIVE = "live"
    DISABLED = "disabled"


class EmployeeStatus(str, Enum):
    ACTIVE = "active"
    TRANSFERRING = "transferring"
    RESIGNED = "resigned"


class EmployeeRole(str, Enum):
    BOSS = "boss"
    MANAGER = "manager"
    EMPLOYEE = "employee"


# ── Task ─────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    SCORED = "scored"
    COMPLETED = "completed"
    OVERDUE = "overdue"


# ── Approval ─────────────────────────────────────────────────────────

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class ApprovalType(str, Enum):
    TEAM_CREATE = "team_create"
    TASK_DISPATCH = "task_dispatch"
    KPI_SCORE = "kpi_score"
    REWARD_CALC = "reward_calc"
    GOAL_SPLIT = "goal_split"
    KNOWLEDGE_CANDIDATE = "knowledge_candidate"
    RISK_ALERT = "risk_alert"
    ESCALATION_BOSS = "escalation_boss"
    CROSS_TEAM_TRIGGER = "cross_team_trigger"
    COACHING_SUGGESTION = "coaching_suggestion"
    EMPLOYEE_TRANSFER = "employee_transfer"


# ── Dispute ──────────────────────────────────────────────────────────

class DisputeStatus(str, Enum):
    FILED = "filed"
    EVIDENCE_COLLECTED = "evidence_collected"
    RULING = "ruling"
    RESOLVED = "resolved"
    OVERTURNED = "overturned"


class DisputeType(str, Enum):
    KPI_SCORE = "kpi_score"
    TASK_QUALITY = "task_quality"
    REWARD = "reward"
    RISK_LABEL = "risk_label"


# ── Goal ─────────────────────────────────────────────────────────────

class GoalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    TRACKING = "tracking"
    ACHIEVED = "achieved"
    FAILED = "failed"


class GoalLevel(str, Enum):
    COMPANY = "company"
    DEPARTMENT = "department"
    PERSONAL = "personal"


# ── KPI ──────────────────────────────────────────────────────────────

class KPIPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class KPIScoreStatus(str, Enum):
    DRAFT = "draft"
    CALCULATED = "calculated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DISPUTED = "disputed"


# ── Reward ───────────────────────────────────────────────────────────

class RewardStatus(str, Enum):
    CALCULATED = "calculated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAID = "paid"


# ── Escalation ───────────────────────────────────────────────────────

class EscalationLevel(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    BOSS = "boss"


# ── Shadow Mode ──────────────────────────────────────────────────────

class ShadowMode(str, Enum):
    SHADOW = "shadow"
    LIVE = "live"


# ── Memory ───────────────────────────────────────────────────────────

class MemoryLayer(str, Enum):
    L1 = "L1"  # System rules (hard constraints)
    L2 = "L2"  # Team SOP / operational rules
    L3 = "L3"  # Employee profile & action cards
    L4 = "L4"  # Business knowledge / case studies
    L5 = "L5"  # Conversation summaries / dialogue memory


class MemoryScenario(str, Enum):
    DAILY_CHAT = "daily_chat"
    KPI_SCORING = "kpi_scoring"
    TASK_ESCALATION = "task_escalation"
    COACHING = "coaching"
    REPORT_GENERATION = "report_generation"
    RISK_WARNING = "risk_warning"
    CUSTOMER_INQUIRY = "customer_inquiry"
    APPROVAL_PROCESSING = "approval_processing"
    DISPUTE_PROCESSING = "dispute_processing"


# ── Sub-Agent Roles ──────────────────────────────────────────────────

class SubAgentRole(str, Enum):
    DIRECTOR = "director"
    ANALYST = "analyst"
    COACH = "coach"
    EXECUTOR = "executor"


# ── Channels ─────────────────────────────────────────────────────────

class Channel(str, Enum):
    FEISHU = "feishu"
    WECOM = "wecom"
    DASHBOARD = "dashboard"


class MessageType(str, Enum):
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    CARD = "card"
    COMMAND = "command"


# ── Knowledge ────────────────────────────────────────────────────────

class KnowledgeScope(str, Enum):
    COMPANY = "company"
    DEPARTMENT = "department"


class KnowledgeSource(str, Enum):
    MANUAL = "manual"
    DREAM = "dream"


class KnowledgeStatus(str, Enum):
    ACTIVE = "active"
    CANDIDATE = "candidate"
    ARCHIVED = "archived"


# ── Skill Source ─────────────────────────────────────────────────────

class SkillSource(str, Enum):
    BUILTIN = "builtin"
    CUSTOM = "custom"
    MCP = "mcp"


# ── Report ───────────────────────────────────────────────────────────

class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ── Decision Log ─────────────────────────────────────────────────────

class ReviewStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    SKIPPED = "skipped"


# ── Automation Profile (Org Maturity Templates) ──────────────────────

class AutomationProfile(str, Enum):
    STARTUP = "startup"           # Boss-direct, few approvals, reminders focus
    MID_MANAGER = "mid_manager"   # Managers handle daily, boss sees exceptions
    PROCESS_DRIVEN = "process_driven"  # Full rules, reward loops, L3/L4 automation


# ── Agent Loop States ────────────────────────────────────────────────

class AgentLoopState(str, Enum):
    IDLE = "idle"
    RECEIVING_INPUT = "receiving_input"
    COMMAND_ROUTING = "command_routing"
    LOADING_CONTEXT = "loading_context"
    THINKING = "thinking"
    CALLING_TOOL = "calling_tool"
    OBSERVING_RESULT = "observing_result"
    RESPONDING = "responding"
    ERROR_HANDLING = "error_handling"
