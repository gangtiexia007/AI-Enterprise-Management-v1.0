import logging
from datetime import datetime, date

from sqlalchemy.orm import Session

from models import Task, KPIRecord, EscalationLog, TaskStatus, Setting

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


def check_overdue_tasks(db: Session) -> int:
    """Mark tasks past their deadline as overdue. Returns count of newly overdue tasks."""
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
    return len(tasks)


def _get_setting(db: Session, key: str, default: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default


def check_escalations(db: Session) -> int:
    """Create escalation logs for overdue tasks. Returns count of new escalations."""
    overdue_tasks = db.query(Task).filter(Task.status == TaskStatus.OVERDUE).all()
    created = 0
    for task in overdue_tasks:
        existing = (
            db.query(EscalationLog)
            .filter(EscalationLog.task_id == task.id)
            .order_by(EscalationLog.sent_at.desc())
            .first()
        )
        if not existing:
            msg = f"任务「{task.title}」已逾期，请尽快处理。"
            db.add(EscalationLog(
                task_id=task.id,
                level="employee",
                message=msg,
            ))
            _try_feishu_notify(task, msg)
            created += 1
        elif existing.level == "employee" and existing.responded == 0:
            msg = f"任务「{task.title}」逾期且负责人未回应，已升级至老板。"
            db.add(EscalationLog(
                task_id=task.id,
                level="boss",
                message=msg,
            ))
            _try_feishu_notify(task, msg)
            created += 1
    if created:
        db.commit()
    return created


def _try_feishu_notify(task: Task, message: str):
    try:
        from harness.feishu_client import feishu_client
        if task.assignee_name:
            days_overdue = (date.today() - task.deadline).days if task.deadline else 0
            feishu_client.send_reminder(getattr(task, 'feishu_id', ''), task.title, days_overdue)
    except Exception as e:
        logger.debug(f"Feishu notification skipped: {e}")


def calculate_kpi_scores(db: Session) -> int:
    """Recalculate scores and grades for KPI records that have actual values. Returns count updated."""
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
