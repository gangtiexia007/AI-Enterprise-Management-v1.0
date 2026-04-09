"""Domain models for all 34 database tables.

These Pydantic models serve as the single source of truth for:
- Database schema (CREATE TABLE SQL generated from these)
- API request/response schemas
- Internal data transfer between modules

Every module imports from here. No module defines its own ad-hoc dicts.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import (
    ApprovalStatus,
    ApprovalType,
    AutomationLevel,
    AutomationProfile,
    Channel,
    Confidence,
    DisputeStatus,
    DisputeType,
    EmployeeRole,
    EmployeeStatus,
    EscalationLevel,
    GoalLevel,
    GoalStatus,
    KnowledgeScope,
    KnowledgeSource,
    KnowledgeStatus,
    KPIPeriod,
    MemoryLayer,
    ReportType,
    ReviewStatus,
    RewardStatus,
    ShadowMode as ShadowModeEnum,
    SkillSource,
    TaskStatus,
    TeamStatus,
    UserTier,
)


def _now() -> datetime:
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════════════════
# 1. CORE TABLES (original 20)
# ═══════════════════════════════════════════════════════════════════════

class Team(BaseModel):
    id: str = Field(..., description="Unique team identifier")
    name: str
    display_name: str = ""
    tier: UserTier = UserTier.T2
    status: TeamStatus = TeamStatus.DRAFT
    department: str = ""
    system_prompt: str = ""
    primary_model: str = ""
    fallback_model: str = ""
    data_scope_json: dict[str, Any] = Field(default_factory=dict)
    knowledge_scope_json: dict[str, Any] = Field(default_factory=dict)
    escalation_json: dict[str, Any] = Field(default_factory=dict)
    automation_profile: AutomationProfile = AutomationProfile.STARTUP
    is_boss_agent: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class TeamBot(BaseModel):
    id: str
    team_id: str
    channel: Channel
    app_id_encrypted: str = ""
    app_secret_encrypted: str = ""
    webhook_url: str = ""
    extra_json: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    verified: bool = False
    created_at: datetime = Field(default_factory=_now)


class Employee(BaseModel):
    id: str
    name: str
    feishu_id: str = ""
    wecom_id: str = ""
    team_id: str = ""
    role: EmployeeRole = EmployeeRole.EMPLOYEE
    department: str = ""
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    direct_manager_id: str = ""
    join_date: date | None = None
    birthday: date | None = None
    contract_end_date: date | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=_now)


class SubAgent(BaseModel):
    id: str
    team_id: str
    name: str
    display_name: str = ""
    role: str = "executor"
    description: str = ""
    system_prompt: str = ""
    skills_json: list[str] = Field(default_factory=list)
    model_override: str = ""
    max_permission: int = 0
    sort_order: int = 0
    created_at: datetime = Field(default_factory=_now)


class Model(BaseModel):
    id: str
    name: str
    provider: str
    api_key_encrypted: str = ""
    capabilities_json: list[str] = Field(default_factory=list)
    cost_tier: int = 1
    daily_token_limit: int = 0
    monthly_token_limit: int = 0
    is_default: bool = False
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)


class ModelUsage(BaseModel):
    id: str
    model_id: str
    team_id: str
    date: date
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Skill(BaseModel):
    id: str
    name: str
    display_name: str = ""
    description: str = ""
    source: SkillSource = SkillSource.BUILTIN
    tools_json: list[dict[str, Any]] = Field(default_factory=list)
    config_json: dict[str, Any] = Field(default_factory=dict)
    is_global: bool = False
    created_at: datetime = Field(default_factory=_now)


class TeamSkill(BaseModel):
    id: str
    team_id: str
    skill_id: str
    assigned_to: str = "main"


class KPIDefinition(BaseModel):
    id: str
    team_id: str
    name: str
    period: KPIPeriod = KPIPeriod.MONTHLY
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    scoring_json: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    target_value: float = 0.0
    source_type: str = ""
    source_detail: str = ""
    responsible_role: str = ""
    update_frequency: str = ""
    dispute_resolver: str = ""
    confidence_baseline: str = ""
    created_at: datetime = Field(default_factory=_now)


class KPIScore(BaseModel):
    id: str
    kpi_def_id: str
    employee_id: str
    period_key: str
    scores_json: dict[str, Any] = Field(default_factory=dict)
    total_score: float = 0.0
    grade: str = ""
    feedback: str = ""
    status: str = "draft"
    scored_at: datetime = Field(default_factory=_now)


class Goal(BaseModel):
    id: str
    parent_id: str = ""
    level: GoalLevel = GoalLevel.PERSONAL
    team_id: str = ""
    employee_id: str = ""
    owner_id: str
    title: str
    target_value: float = 0.0
    current_value: float = 0.0
    unit: str = ""
    period: str = ""
    start_date: date | None = None
    end_date: date | None = None
    status: GoalStatus = GoalStatus.DRAFT
    created_at: datetime = Field(default_factory=_now)


class Task(BaseModel):
    id: str
    template_id: str = ""
    team_id: str
    employee_id: str = ""
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    dispatched_at: datetime | None = None
    deadline_at: datetime | None = None
    completed_at: datetime | None = None
    score: float | None = None
    score_timeliness: float | None = None
    score_quality: float | None = None
    score_complexity: float | None = None
    grade: str = ""
    feedback: str = ""
    depends_on_task_ids: str = ""
    blocked_reason: str = ""
    unblocked_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)


class TaskFeedback(BaseModel):
    id: str
    task_id: str
    employee_id: str
    content: str = ""
    file_path: str = ""
    feedback_type: str = "text"
    submitted_at: datetime = Field(default_factory=_now)


class Escalation(BaseModel):
    id: str
    task_id: str
    level: EscalationLevel = EscalationLevel.EMPLOYEE
    target_id: str
    message: str = ""
    sent_at: datetime = Field(default_factory=_now)
    response_at: datetime | None = None


class Memory(BaseModel):
    id: str
    layer: MemoryLayer = MemoryLayer.L5
    team_id: str = ""
    employee_id: str = ""
    content: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    created_by: str = ""
    reference_count: int = 0
    last_referenced_at: datetime | None = None
    is_verified: bool = False
    created_at: datetime = Field(default_factory=_now)
    expires_at: datetime | None = None


class Knowledge(BaseModel):
    id: str
    title: str
    content: str
    scope: KnowledgeScope = KnowledgeScope.COMPANY
    department: str = ""
    category: str = ""
    source: KnowledgeSource = KnowledgeSource.MANUAL
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    created_by: str = ""
    created_at: datetime = Field(default_factory=_now)


class DecisionLog(BaseModel):
    id: str
    team_id: str = ""
    employee_id: str
    decision: str
    data_basis: str = ""
    expected_result: str = ""
    actual_result: str = ""
    evaluation: str = ""
    tracked_metrics_json: dict[str, Any] = Field(default_factory=dict)
    metric_snapshot_before: dict[str, Any] = Field(default_factory=dict)
    metric_snapshot_after: dict[str, Any] = Field(default_factory=dict)
    review_status: ReviewStatus = ReviewStatus.PENDING
    review_result: str = ""
    created_at: datetime = Field(default_factory=_now)


class AuditLog(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=_now)
    actor: str
    team_id: str = ""
    action: str
    resource_type: str = ""
    resource_id: str = ""
    details_json: dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    id: str
    team_id: str
    employee_id: str = ""
    channel: Channel = Channel.DASHBOARD
    turns_json: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class DreamReport(BaseModel):
    id: str
    team_id: str = ""
    date: date
    report_type: ReportType = ReportType.DAILY
    summary: str = ""
    stats_json: dict[str, Any] = Field(default_factory=dict)
    knowledge_candidates_json: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class DashboardUser(BaseModel):
    id: str
    username: str
    password_hash: str
    tier: UserTier = UserTier.T1
    department: str = ""
    display_name: str = ""
    employee_id: str = ""
    created_at: datetime = Field(default_factory=_now)


# ═══════════════════════════════════════════════════════════════════════
# 2. EXTENDED TABLES (14 new)
# ═══════════════════════════════════════════════════════════════════════

class HiringProfile(BaseModel):
    id: str
    team_id: str
    profile_json: dict[str, Any] = Field(default_factory=dict)
    source: str = "auto"
    created_at: datetime = Field(default_factory=_now)


class InterviewTemplate(BaseModel):
    id: str
    team_id: str
    position: str = ""
    required_questions: list[str] = Field(default_factory=list)
    optional_questions: list[str] = Field(default_factory=list)
    scoring_criteria_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class Candidate(BaseModel):
    id: str
    team_id: str
    name: str
    position: str = ""
    resume_summary: str = ""
    interview_scores_json: dict[str, Any] = Field(default_factory=dict)
    overall_score: float = 0.0
    status: str = "pending"
    created_at: datetime = Field(default_factory=_now)


class OnboardingPlan(BaseModel):
    id: str
    team_id: str
    employee_id: str
    plan_json: dict[str, Any] = Field(default_factory=dict)
    progress: float = 0.0
    status: str = "active"
    created_at: datetime = Field(default_factory=_now)


class Customer(BaseModel):
    id: str
    team_id: str
    name: str
    company: str = ""
    contact_info: str = ""
    profile_json: dict[str, Any] = Field(default_factory=dict)
    assigned_employee_id: str = ""
    scope: str = "isolated"
    status: str = "active"
    created_at: datetime = Field(default_factory=_now)


class CustomerContact(BaseModel):
    id: str
    customer_id: str
    employee_id: str
    content: str
    contact_type: str = "note"
    created_at: datetime = Field(default_factory=_now)


class CustomerFeedback(BaseModel):
    id: str
    customer_id: str
    feedback_type: str = "general"
    content: str
    status: str = "open"
    created_at: datetime = Field(default_factory=_now)


class TaskDependency(BaseModel):
    id: str
    upstream_task_id: str
    downstream_task_id: str
    dependency_type: str = "finish_to_start"
    status: str = "waiting"
    created_at: datetime = Field(default_factory=_now)


class RewardRule(BaseModel):
    id: str
    team_id: str
    name: str
    kpi_grade: str
    formula: str
    description: str = ""
    created_at: datetime = Field(default_factory=_now)


class RewardCalculation(BaseModel):
    id: str
    employee_id: str
    team_id: str
    period: str
    kpi_score_id: str = ""
    rule_id: str = ""
    calculated_amount: float = 0.0
    formula_used: str = ""
    variables_json: dict[str, Any] = Field(default_factory=dict)
    status: RewardStatus = RewardStatus.CALCULATED
    approved_by: str = ""
    created_at: datetime = Field(default_factory=_now)


class ApprovalRequest(BaseModel):
    id: str
    type: ApprovalType
    team_id: str = ""
    title: str
    detail_json: dict[str, Any] = Field(default_factory=dict)
    suggestion: str = ""
    reasoning: str = ""
    priority: int = 2
    automation_level: AutomationLevel = AutomationLevel.L2
    confidence: Confidence = Confidence.B
    status: ApprovalStatus = ApprovalStatus.PENDING
    source_agent: str = ""
    requester_id: str = ""
    approver_id: str = ""
    auto_rule_matched: str = ""
    rejection_reason: str = ""
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None


class ShadowResult(BaseModel):
    id: str
    team_id: str
    result_type: str
    original_action_json: dict[str, Any] = Field(default_factory=dict)
    shadow_data_json: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence = Confidence.B
    would_have_done: str = ""
    created_at: datetime = Field(default_factory=_now)


class TeamShadowConfig(BaseModel):
    id: str
    team_id: str
    mode: ShadowModeEnum = ShadowModeEnum.SHADOW
    shadow_start_date: datetime | None = None
    shadow_duration_days: int = 7
    switched_live_at: datetime | None = None


class Dispute(BaseModel):
    id: str
    type: DisputeType
    team_id: str = ""
    employee_id: str
    target_type: str = ""
    target_id: str = ""
    original_data_json: dict[str, Any] = Field(default_factory=dict)
    ai_reasoning: str = ""
    employee_reason: str = ""
    evidence_json: list[dict[str, Any]] = Field(default_factory=list)
    resolution: str = ""
    resolver_id: str = ""
    status: DisputeStatus = DisputeStatus.FILED
    rule_correction_suggestion: str = ""
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None


# ═══════════════════════════════════════════════════════════════════════
# 3. MESSAGE / RESPONSE CONTRACTS
# ═══════════════════════════════════════════════════════════════════════

class UnifiedMessage(BaseModel):
    channel: Channel
    sender_id: str
    team_id: str = ""
    employee_id: str = ""
    content: str = ""
    msg_type: str = "text"
    file_url: str = ""
    file_path: str = ""
    file_name: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)


class AgentResponse(BaseModel):
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    card_json: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
