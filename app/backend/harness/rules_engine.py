"""
Rule Engine — deterministic logic that doesn't need AI.

Handles: overdue detection, escalation cascade, KPI scoring,
approval timeouts, KPI alerts, status change notifications.
"""
import json
import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from models import (
    Task, KPIRecord, EscalationLog, TaskStatus, Setting,
    Approval, ApprovalStatus, AuditLog, Employee,
)

logger = logging.getLogger(__name__)


def _calc_grade(score: float) -> str:
    if score >= 120:
        return "S"
    elif score >= 100:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 60:
        return "C"
    return "D"


def _get_setting(db: Session, key: str, default: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default


def _get_escalation_intervals(db: Session) -> list[int]:
    raw = _get_setting(db, "escalation_intervals", "24,48,72")
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return [24, 48, 72]


# ───── Core Rules ─────

def check_overdue_tasks(db: Session) -> int:
    """Mark tasks past their deadline as overdue."""
    today = date.today()
    tasks = (
        db.query(Task)
        .filter(
            Task.deadline < today,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED, TaskStatus.OVERDUE]),
        )
        .all()
    )
    for task in tasks:
        task.status = TaskStatus.OVERDUE
        task.updated_at = datetime.utcnow()
    if tasks:
        db.commit()
        _notify_status_change(db, tasks, "overdue")
    return len(tasks)


def check_escalations(db: Session) -> int:
    """Multi-level escalation with configurable intervals."""
    overdue_tasks = db.query(Task).filter(Task.status == TaskStatus.OVERDUE).all()
    intervals = _get_escalation_intervals(db)
    created = 0

    for task in overdue_tasks:
        days_overdue = (date.today() - task.deadline).days if task.deadline else 0
        existing = (
            db.query(EscalationLog)
            .filter(EscalationLog.task_id == task.id)
            .order_by(EscalationLog.sent_at.desc())
            .first()
        )

        if not existing:
            msg = f"任务「{task.title}」已逾期 {days_overdue} 天，请尽快处理。"
            db.add(EscalationLog(task_id=task.id, level="employee", message=msg))
            _try_feishu_reminder(task, days_overdue)
            created += 1

        elif existing.level == "employee" and existing.responded == 0:
            hours_since = (datetime.utcnow() - existing.sent_at).total_seconds() / 3600
            threshold = intervals[1] if len(intervals) > 1 else 48
            if hours_since >= threshold:
                msg = f"任务「{task.title}」逾期 {days_overdue} 天且负责人未回应，已升级至老板。"
                db.add(EscalationLog(task_id=task.id, level="boss", message=msg))
                _try_feishu_boss_notify(db, task, msg)
                _create_overdue_approval(db, task, days_overdue)
                created += 1

        elif existing.level == "boss" and existing.responded == 0:
            hours_since = (datetime.utcnow() - existing.sent_at).total_seconds() / 3600
            threshold = intervals[2] if len(intervals) > 2 else 72
            if hours_since >= threshold:
                msg = f"⚠️ 紧急: 任务「{task.title}」逾期 {days_overdue} 天，已多次催办无响应。"
                db.add(EscalationLog(task_id=task.id, level="urgent", message=msg))
                _try_feishu_boss_notify(db, task, msg)
                created += 1

    if created:
        db.commit()
    return created


def calculate_kpi_scores(db: Session) -> int:
    """Recalculate KPI scores and grades."""
    records = (
        db.query(KPIRecord)
        .filter(KPIRecord.actual_value > 0, KPIRecord.target_value > 0)
        .all()
    )
    updated = 0
    for r in records:
        new_score = round(r.actual_value / r.target_value * 100, 1)
        new_grade = _calc_grade(new_score)
        if r.score != new_score or r.grade != new_grade:
            r.score = new_score
            r.grade = new_grade
            updated += 1
    if updated:
        db.commit()
    return updated


# ───── P1 Rules ─────

def check_approval_timeouts(db: Session) -> int:
    """48h reminder → 72h auto-escalation for pending approvals."""
    pending = db.query(Approval).filter(Approval.status == ApprovalStatus.PENDING).all()
    acted = 0
    now = datetime.utcnow()

    for a in pending:
        hours_pending = (now - a.created_at).total_seconds() / 3600
        if hours_pending >= 72:
            db.add(AuditLog(
                action="approval_auto_escalate",
                detail=f"审批「{a.title}」超过72小时未处理，已自动标记为紧急",
                actor="rules_engine",
                resource_type="approval",
                resource_id=str(a.id),
            ))
            a.priority = max(a.priority, 1)
            _try_feishu_boss_text(db, f"⚠️ 审批超时提醒: 「{a.title}」已等待 {int(hours_pending)} 小时，请尽快处理。")
            acted += 1
        elif hours_pending >= 48:
            existing_reminder = db.query(AuditLog).filter(
                AuditLog.action == "approval_timeout_reminder",
                AuditLog.resource_id == str(a.id),
            ).first()
            if not existing_reminder:
                db.add(AuditLog(
                    action="approval_timeout_reminder",
                    detail=f"审批「{a.title}」已等待超过48小时",
                    actor="rules_engine",
                    resource_type="approval",
                    resource_id=str(a.id),
                ))
                _try_feishu_boss_text(db, f"📌 审批提醒: 「{a.title}」已等待 {int(hours_pending)} 小时")
                acted += 1

    if acted:
        db.commit()
    return acted


def check_kpi_alerts(db: Session) -> int:
    """Flag employees with KPI scores below threshold."""
    threshold = float(_get_setting(db, "kpi_alert_threshold", "60"))
    records = (
        db.query(KPIRecord)
        .filter(KPIRecord.score > 0, KPIRecord.score < threshold)
        .all()
    )
    alerted = 0
    seen_employees = set()
    for r in records:
        if r.employee_name in seen_employees:
            continue
        seen_employees.add(r.employee_name)
        existing = db.query(AuditLog).filter(
            AuditLog.action == "kpi_alert",
            AuditLog.resource_id == str(r.employee_id),
            AuditLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
        ).first()
        if not existing:
            db.add(AuditLog(
                action="kpi_alert",
                detail=f"{r.employee_name} 的 KPI 指标「{r.metric_name}」得分 {r.score} 低于阈值 {threshold}",
                actor="rules_engine",
                resource_type="kpi",
                resource_id=str(r.employee_id),
            ))
            _try_feishu_boss_text(db, f"📉 KPI 预警: {r.employee_name} 的「{r.metric_name}」得分 {r.score}，低于阈值 {threshold}")
            alerted += 1

    if alerted:
        db.commit()
    return alerted


# ───── Helpers ─────

def _notify_status_change(db: Session, tasks: list, new_status: str):
    """Send status change notifications for relevant parties."""
    try:
        from harness.feishu_client import feishu_client
        for task in tasks:
            emp = db.query(Employee).filter(Employee.id == task.assignee_id).first() if task.assignee_id else None
            if emp and emp.feishu_id:
                feishu_client.send_status_notification(
                    emp.feishu_id,
                    f"任务状态变更: {task.title}",
                    f"状态已变更为: {new_status}",
                )
    except Exception as e:
        logger.debug(f"Status notification skipped: {e}")


def _try_feishu_reminder(task: Task, days_overdue: int):
    try:
        from harness.feishu_client import feishu_client
        from database import SessionLocal
        db = SessionLocal()
        try:
            emp = db.query(Employee).filter(Employee.id == task.assignee_id).first() if task.assignee_id else None
            if emp and emp.feishu_id:
                feishu_client.send_reminder(emp.feishu_id, task.title, days_overdue, assignee=emp.name)
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"Feishu reminder skipped: {e}")


def _try_feishu_boss_notify(db: Session, task: Task, message: str):
    try:
        from harness.feishu_client import feishu_client
        boss_id = _get_setting(db, "feishu_boss_id")
        if boss_id:
            days = (date.today() - task.deadline).days if task.deadline else 0
            feishu_client.send_approval_request(boss_id, task.title, message)
    except Exception as e:
        logger.debug(f"Feishu boss notify skipped: {e}")


def _try_feishu_boss_text(db: Session, text: str):
    try:
        from harness.feishu_client import feishu_client
        boss_id = _get_setting(db, "feishu_boss_id")
        if boss_id:
            feishu_client.send_text_message(boss_id, text)
    except Exception as e:
        logger.debug(f"Feishu boss text skipped: {e}")


def _create_overdue_approval(db: Session, task: Task, days_overdue: int):
    """Create an approval entry when a task is critically overdue."""
    existing = db.query(Approval).filter(
        Approval.title.contains(task.title),
        Approval.status == ApprovalStatus.PENDING,
    ).first()
    if existing:
        return

    db.add(Approval(
        type="overdue_task",
        title=f"逾期处理: {task.title}",
        detail=f"任务「{task.title}」已逾期 {days_overdue} 天，负责人 {task.assignee_name or '未指派'} 未回应。请决定: 延期/重新分配/取消。",
        priority=1,
        status=ApprovalStatus.PENDING,
    ))
