from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Task, Goal, KPIRecord, Knowledge, Employee, TaskStatus, Approval, ApprovalStatus
from schemas import DashboardStats

router = APIRouter()


@router.get("/daily")
def daily_report(db: Session = Depends(get_db)):
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())

    total = db.query(Task).count()
    done = db.query(Task).filter(
        Task.status == TaskStatus.DONE,
        Task.updated_at >= start_of_day,
    ).count()
    overdue = db.query(Task).filter(
        Task.deadline < today,
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
    ).count()
    pending = db.query(Task).filter(Task.status == TaskStatus.PENDING).count()

    top_performers = (
        db.query(
            Task.assignee_name,
            func.count(Task.id).label("completed"),
        )
        .filter(Task.status == TaskStatus.DONE, Task.updated_at >= start_of_day)
        .group_by(Task.assignee_name)
        .order_by(func.count(Task.id).desc())
        .limit(5)
        .all()
    )

    overdue_items = (
        db.query(Task)
        .filter(
            Task.deadline < today,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
        )
        .all()
    )

    return {
        "date": today.isoformat(),
        "total_tasks": total,
        "completed_today": done,
        "overdue_count": overdue,
        "pending_count": pending,
        "top_performers": [
            {"name": r.assignee_name or "未分配", "completed": r.completed}
            for r in top_performers
        ],
        "overdue_items": [
            {"id": t.id, "title": t.title, "assignee": t.assignee_name, "deadline": t.deadline.isoformat() if t.deadline else None}
            for t in overdue_items
        ],
    }


@router.get("/weekly")
def weekly_report(db: Session = Depends(get_db)):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    start_dt = datetime.combine(week_start, datetime.min.time())

    total = db.query(Task).filter(Task.created_at >= start_dt).count()
    done = db.query(Task).filter(
        Task.status == TaskStatus.DONE,
        Task.updated_at >= start_dt,
    ).count()
    overdue = db.query(Task).filter(
        Task.deadline < today,
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
    ).count()

    top_performers = (
        db.query(
            Task.assignee_name,
            func.count(Task.id).label("completed"),
        )
        .filter(Task.status == TaskStatus.DONE, Task.updated_at >= start_dt)
        .group_by(Task.assignee_name)
        .order_by(func.count(Task.id).desc())
        .limit(5)
        .all()
    )

    overdue_items = (
        db.query(Task)
        .filter(
            Task.deadline < today,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
        )
        .all()
    )

    return {
        "week_start": week_start.isoformat(),
        "week_end": today.isoformat(),
        "total_tasks_this_week": total,
        "completed_this_week": done,
        "overdue_count": overdue,
        "top_performers": [
            {"name": r.assignee_name or "未分配", "completed": r.completed}
            for r in top_performers
        ],
        "overdue_items": [
            {"id": t.id, "title": t.title, "assignee": t.assignee_name, "deadline": t.deadline.isoformat() if t.deadline else None}
            for t in overdue_items
        ],
    }


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    today = date.today()
    total_tasks = db.query(Task).count()
    overdue_tasks = db.query(Task).filter(
        Task.deadline < today,
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
    ).count()
    pending_tasks = db.query(Task).filter(Task.status == TaskStatus.PENDING).count()
    completed_tasks = db.query(Task).filter(Task.status == TaskStatus.DONE).count()
    in_progress_tasks = db.query(Task).filter(Task.status == TaskStatus.IN_PROGRESS).count()

    goals = db.query(Goal).filter(Goal.target_value > 0).all()
    if goals:
        goal_progress = round(
            sum(g.current_value / g.target_value for g in goals) / len(goals) * 100, 1
        )
    else:
        goal_progress = 0

    avg_score = db.query(func.avg(KPIRecord.score)).scalar()
    knowledge_count = db.query(Knowledge).count()
    employee_count = db.query(Employee).count()
    pending_approvals = db.query(Approval).filter(Approval.status == ApprovalStatus.PENDING).count()

    return DashboardStats(
        total_tasks=total_tasks,
        overdue_tasks=overdue_tasks,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        goal_progress=goal_progress,
        avg_kpi_score=round(avg_score, 1) if avg_score else 0,
        knowledge_count=knowledge_count,
        employee_count=employee_count,
        pending_approvals=pending_approvals,
    )


@router.get("/token-usage")
def get_token_usage(days: int = 7, db: Session = Depends(get_db)):
    from models import TokenUsage
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    records = db.query(TokenUsage).filter(TokenUsage.created_at >= cutoff).order_by(TokenUsage.created_at.desc()).all()
    total_tokens = sum(r.total_tokens for r in records)
    total_cost = sum(r.cost for r in records)
    return {"total_tokens": total_tokens, "total_cost": total_cost, "record_count": len(records)}


@router.get("/token-budget")
def get_token_budget():
    from harness.token_budget import token_budget_manager
    return {
        "monthly": token_budget_manager.get_or_create_monthly(),
        "daily": token_budget_manager.get_or_create_daily(),
    }


@router.put("/token-budget")
def update_token_budget(data: dict, db: Session = Depends(get_db)):
    from models import Setting
    if "monthly" in data:
        s = db.query(Setting).filter(Setting.key == "token_budget_monthly").first()
        if s:
            s.value = str(data["monthly"])
        else:
            db.add(Setting(key="token_budget_monthly", value=str(data["monthly"])))
    if "daily" in data:
        s = db.query(Setting).filter(Setting.key == "token_budget_daily").first()
        if s:
            s.value = str(data["daily"])
        else:
            db.add(Setting(key="token_budget_daily", value=str(data["daily"])))
    db.commit()
    return {"message": "Budget updated"}


@router.get("/token-usage-summary")
def get_token_usage_summary(days: int = 30):
    from harness.token_budget import token_budget_manager
    return token_budget_manager.get_usage_summary(days)
