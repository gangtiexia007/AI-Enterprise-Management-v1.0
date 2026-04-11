"""Tasks router — CRUD + dispatch + feedback + auto-chain + templates."""
import json
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Task, Feedback, TaskStatus, Employee
from schemas import TaskCreate, TaskUpdate, TaskOut, FeedbackCreate, FeedbackOut, TASK_TEMPLATES

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/templates")
def list_templates():
    return {k: {kk: vv for kk, vv in v.items() if kk != "auto_next_config"}
            for k, v in TASK_TEMPLATES.items()}


@router.get("", response_model=List[TaskOut])
def list_tasks(
    status: Optional[str] = None,
    assignee_name: Optional[str] = None,
    task_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if status:
        q = q.filter(Task.status == status)
    if assignee_name:
        q = q.filter(Task.assignee_name.contains(assignee_name))
    if task_type:
        q = q.filter(Task.task_type == task_type)
    return q.order_by(Task.created_at.desc()).all()


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskOut)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    tpl_name = data.get("task_type", "")
    if tpl_name in TASK_TEMPLATES and not data.get("auto_next_config"):
        tpl = TASK_TEMPLATES[tpl_name]
        data["auto_next_config"] = tpl.get("auto_next_config", "")
        if not data.get("description"):
            data["description"] = tpl.get("description", "")
        if not data.get("priority") or data["priority"] == "normal":
            data["priority"] = tpl.get("priority", "normal")
        if not data.get("deadline") and tpl.get("deadline_offset_days"):
            data["deadline"] = date.today() + timedelta(days=tpl["deadline_offset_days"])
    task = Task(**data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status.value if hasattr(task.status, 'value') else task.status
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(task, field, value)
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    new_status = task.status.value if hasattr(task.status, 'value') else task.status
    if old_status != "done" and new_status == "done":
        _trigger_auto_chain(task, db)

    return task


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"detail": "deleted"}


@router.post("/{task_id}/dispatch", response_model=TaskOut)
def dispatch_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.DISPATCHED
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    if task.assignee_id:
        emp = db.query(Employee).filter(Employee.id == task.assignee_id).first()
        if emp and emp.feishu_id:
            try:
                from harness.feishu_client import feishu_client
                feishu_client.send_task_notification(
                    emp.feishu_id,
                    task.title,
                    description=task.description or "",
                    deadline=str(task.deadline) if task.deadline else "",
                    assignee=emp.name,
                )
            except Exception:
                pass

    return task


@router.post("/{task_id}/feedback", response_model=FeedbackOut)
def submit_feedback(task_id: int, body: FeedbackCreate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    feedback = Feedback(
        task_id=task_id,
        employee_id=body.employee_id,
        content=body.content,
        files=body.files,
    )
    db.add(feedback)
    task.status = TaskStatus.FEEDBACK_SUBMITTED
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(feedback)
    return feedback


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    """Mark task done and trigger auto-chain."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.DONE
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    _trigger_auto_chain(task, db)
    return task


def _trigger_auto_chain(completed_task: Task, db: Session):
    """When a task completes, auto-create the next task in the chain."""
    config_raw = completed_task.auto_next_config or ""
    if not config_raw.strip():
        return

    try:
        config = json.loads(config_raw)
    except json.JSONDecodeError:
        return

    next_type = config.get("next_type", "")
    if not next_type:
        return

    context = (completed_task.title.split("：", 1)[-1]
               if "：" in completed_task.title
               else completed_task.title)

    title_tpl = config.get("title_template", f"{next_type}：{{context}}")
    desc_tpl = config.get("description_template", "")
    title = title_tpl.replace("{context}", context)
    desc = desc_tpl.replace("{context}", context)

    offset_hours = config.get("deadline_offset_hours", 72)
    deadline = (datetime.utcnow() + timedelta(hours=offset_hours)).date()

    dept = config.get("assignee_department", "")
    assignee = None
    if dept:
        assignee = db.query(Employee).filter(Employee.department == dept).first()

    tpl = TASK_TEMPLATES.get(next_type, {})
    next_auto = tpl.get("auto_next_config", "")

    new_task = Task(
        title=title,
        description=desc,
        task_type=next_type,
        parent_task_id=completed_task.id,
        auto_next_config=next_auto,
        assignee_id=assignee.id if assignee else None,
        assignee_name=assignee.name if assignee else "",
        deadline=deadline,
        priority=config.get("priority", "high"),
        status=TaskStatus.DISPATCHED,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    logger.info(f"Auto-chain: '{completed_task.title}' → '{new_task.title}' (id={new_task.id})")

    if assignee and assignee.feishu_id:
        try:
            from harness.feishu_client import feishu_client
            feishu_client.send_task_notification(
                assignee.feishu_id,
                new_task.title,
                description=desc,
                deadline=str(deadline),
                assignee=assignee.name,
            )
        except Exception:
            pass

    from models import AuditLog
    db.add(AuditLog(
        action="task_auto_chain",
        detail=f"任务完成自动触发：{completed_task.title} → {new_task.title}",
        actor="system",
        resource_type="task",
        resource_id=str(new_task.id),
    ))
    db.commit()
