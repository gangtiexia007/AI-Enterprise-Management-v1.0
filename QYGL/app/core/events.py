"""Global event contract — all EventBus event names.

Naming: {domain}.{action}
Every event emitted in the system MUST use a constant from this module.
"""


class Events:
    # ── Team ─────────────────────────────────────────────────────────
    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    TEAM_DISABLED = "team.disabled"
    TEAM_SHADOW_STARTED = "team.shadow_started"
    TEAM_SWITCHED_LIVE = "team.switched_live"

    # ── Employee ─────────────────────────────────────────────────────
    EMPLOYEE_JOINED = "employee.joined"
    EMPLOYEE_TRANSFERRED = "employee.transferred"
    EMPLOYEE_RESIGNED = "employee.resigned"
    EMPLOYEE_BIRTHDAY = "employee.birthday"
    EMPLOYEE_CONTRACT_EXPIRING = "employee.contract_expiring"

    # ── Task ─────────────────────────────────────────────────────────
    TASK_CREATED = "task.created"
    TASK_DISPATCHED = "task.dispatched"
    TASK_SUBMITTED = "task.submitted"
    TASK_SCORED = "task.scored"
    TASK_COMPLETED = "task.completed"
    TASK_OVERDUE = "task.overdue"

    # ── KPI ──────────────────────────────────────────────────────────
    KPI_SCORED = "kpi.scored"
    KPI_APPROVED = "kpi.approved"
    KPI_DISPUTED = "kpi.disputed"

    # ── Goal ─────────────────────────────────────────────────────────
    GOAL_CREATED = "goal.created"
    GOAL_PROGRESS_UPDATED = "goal.progress_updated"
    GOAL_ACHIEVED = "goal.achieved"
    GOAL_FAILED = "goal.failed"

    # ── Escalation ───────────────────────────────────────────────────
    ESCALATION_LEVEL1 = "escalation.level1"
    ESCALATION_LEVEL2 = "escalation.level2"
    ESCALATION_LEVEL3 = "escalation.level3"

    # ── Approval ─────────────────────────────────────────────────────
    APPROVAL_SUBMITTED = "approval.submitted"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"
    APPROVAL_WITHDRAWN = "approval.withdrawn"

    # ── Shadow Mode ──────────────────────────────────────────────────
    SHADOW_STARTED = "shadow.started"
    SHADOW_REPORT_GENERATED = "shadow.report_generated"
    SHADOW_SWITCHED_LIVE = "shadow.switched_live"

    # ── Dispute ──────────────────────────────────────────────────────
    DISPUTE_FILED = "dispute.filed"
    DISPUTE_RESOLVED = "dispute.resolved"
    DISPUTE_OVERTURNED = "dispute.overturned"

    # ── Dream Engine ─────────────────────────────────────────────────
    DREAM_DISTILL_COMPLETED = "dream.distill_completed"
    DREAM_KNOWLEDGE_CANDIDATE = "dream.knowledge_candidate"
    DREAM_REPORT_GENERATED = "dream.report_generated"

    # ── Reward ───────────────────────────────────────────────────────
    REWARD_CALCULATED = "reward.calculated"
    REWARD_APPROVED = "reward.approved"
    REWARD_PAID = "reward.paid"

    # ── Customer ─────────────────────────────────────────────────────
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_FEEDBACK = "customer.feedback"
    CUSTOMER_CHURN_WARNING = "customer.churn_warning"

    # ── Decision ─────────────────────────────────────────────────────
    DECISION_RECORDED = "decision.recorded"
    DECISION_TRACKED = "decision.tracked"
    DECISION_REVIEWED = "decision.reviewed"

    # ── Hiring ───────────────────────────────────────────────────────
    HIRING_PROFILE_CREATED = "hiring.profile_created"
    HIRING_CANDIDATE_SCORED = "hiring.candidate_scored"
    HIRING_ONBOARDING_STARTED = "hiring.onboarding_started"

    # ── Cross-Team ───────────────────────────────────────────────────
    CROSS_TEAM_UPSTREAM_COMPLETED = "cross_team.upstream_completed"
    CROSS_TEAM_BOTTLENECK_DETECTED = "cross_team.bottleneck_detected"

    # ── Notification ─────────────────────────────────────────────────
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_MERGED = "notification.merged"

    # ── Model / Token ────────────────────────────────────────────────
    MODEL_BUDGET_WARNING = "model.budget_warning"
    MODEL_BUDGET_EXCEEDED = "model.budget_exceeded"
    MODEL_FALLBACK_TRIGGERED = "model.fallback_triggered"
