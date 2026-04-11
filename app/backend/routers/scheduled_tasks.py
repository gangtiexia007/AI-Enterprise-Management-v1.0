"""Scheduled tasks management router."""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ScheduledTask
from schemas import ScheduledTaskCreate, ScheduledTaskUpdate, ScheduledTaskOut

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_defaults(db: Session):
    """Create default scheduled tasks if none exist."""
    if db.query(ScheduledTask).count() > 0:
        return

    defaults = [
        ScheduledTask(name="每日管理简报", task_type="daily_report", cron_expression="09:00", enabled=1),
        ScheduledTask(name="周度汇总报告", task_type="weekly_report", cron_expression="每周一 09:30", enabled=1),
        ScheduledTask(name="AI 辅导建议", task_type="coaching", cron_expression="每周五 18:00", enabled=1),
        ScheduledTask(name="记忆蒸馏", task_type="memory_distill", cron_expression="每日 02:00", enabled=1),
        ScheduledTask(name="Token 预算检查", task_type="token_budget", cron_expression="每6小时", enabled=1),
        ScheduledTask(name="审批超时检查", task_type="approval_timeout", cron_expression="每4小时", enabled=1),
        ScheduledTask(name="KPI 预警检查", task_type="kpi_alert", cron_expression="每12小时", enabled=1),
    ]
    for d in defaults:
        db.add(d)
    db.commit()


@router.get("", response_model=List[ScheduledTaskOut])
def list_scheduled_tasks(db: Session = Depends(get_db)):
    _ensure_defaults(db)
    return db.query(ScheduledTask).order_by(ScheduledTask.id).all()


@router.post("", response_model=ScheduledTaskOut)
def create_scheduled_task(body: ScheduledTaskCreate, db: Session = Depends(get_db)):
    task = ScheduledTask(**body.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=ScheduledTaskOut)
def update_scheduled_task(task_id: int, body: ScheduledTaskUpdate, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/toggle")
def toggle_scheduled_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Not found")
    task.enabled = 0 if task.enabled else 1
    db.commit()

    from harness.scheduler import get_scheduler, TASK_TYPE_TO_JOB_ID
    sched = get_scheduler()
    if sched:
        job_id = TASK_TYPE_TO_JOB_ID.get(task.task_type)
        if job_id:
            try:
                if task.enabled:
                    sched.resume_job(job_id)
                else:
                    sched.pause_job(job_id)
            except Exception as e:
                logger.warning(f"Failed to pause/resume job {job_id}: {e}")

    return {"id": task.id, "name": task.name, "enabled": task.enabled}


@router.delete("/{task_id}")
def delete_scheduled_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(task)
    db.commit()
    return {"detail": "deleted"}


@router.post("/{task_id}/run")
def run_scheduled_task_now(task_id: int, db: Session = Depends(get_db)):
    """Manually trigger a scheduled task immediately."""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Not found")

    from datetime import datetime
    from harness import scheduler as sched_module

    runners = {
        "daily_report": sched_module._run_daily_report_push,
        "weekly_report": sched_module._run_weekly_report_push,
        "coaching": sched_module._run_coaching_suggestions,
        "memory_distill": sched_module._run_memory_distillation,
        "token_budget": sched_module._run_token_budget_check,
        "approval_timeout": sched_module._run_approval_timeout_check,
        "kpi_alert": sched_module._run_kpi_alert_check,
    }

    runner = runners.get(task.task_type)
    if not runner:
        return {"error": f"Unknown task type: {task.task_type}"}

    try:
        runner()
        task.last_run = datetime.utcnow()
        db.commit()
        return {"message": f"任务 '{task.name}' 已执行", "last_run": str(task.last_run)}
    except Exception as e:
        return {"error": str(e)}
