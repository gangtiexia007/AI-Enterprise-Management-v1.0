"""Builtin skills for reports and data summaries."""
from datetime import date
from sqlalchemy import func
from harness.skill_registry import tool, ToolResult


@tool(
    name="daily_report",
    description="生成每日管理简报（任务统计、目标达成率等）",
    permission_level=0,
)
async def daily_report(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus, Goal
    total = db_session.query(Task).count()
    done_today = db_session.query(Task).filter(
        Task.status == TaskStatus.DONE,
        func.date(Task.updated_at) == date.today()
    ).count()
    overdue = db_session.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).count()
    pending = db_session.query(Task).filter(Task.status == TaskStatus.PENDING).count()
    goals = db_session.query(Goal).all()
    goal_progress = 0
    if goals:
        progresses = [(g.current_value / g.target_value * 100) if g.target_value > 0 else 0 for g in goals]
        goal_progress = round(sum(progresses) / len(progresses))

    try:
        from models import PodOrder
        today_orders = db_session.query(PodOrder).filter(
            func.date(PodOrder.order_date) == date.today()
        ).count()
        today_valid = db_session.query(PodOrder).filter(
            func.date(PodOrder.order_date) == date.today(),
            PodOrder.status_category == "valid",
        ).count()
        today_gmv = db_session.query(func.sum(PodOrder.paid_amount_cny)).filter(
            func.date(PodOrder.order_date) == date.today(),
            PodOrder.status_category == "valid",
        ).scalar() or 0
    except Exception:
        today_orders = 0
        today_valid = 0
        today_gmv = 0

    return ToolResult(success=True, data={
        "date": str(date.today()),
        "total_tasks": total,
        "done_today": done_today,
        "overdue": overdue,
        "pending": pending,
        "goal_progress": goal_progress,
        "pod_today_orders": today_orders,
        "pod_today_valid": today_valid,
        "pod_today_gmv": round(today_gmv, 2),
    })


@tool(
    name="data_summary",
    description="获取企业核心数据摘要（任务+目标概况）",
    permission_level=0,
)
async def data_summary(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus, Goal, Employee, KPIRecord
    total_tasks = db_session.query(Task).count()
    overdue = db_session.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).count()
    pending = db_session.query(Task).filter(Task.status == TaskStatus.PENDING).count()
    done = db_session.query(Task).filter(Task.status == TaskStatus.DONE).count()
    emp_count = db_session.query(Employee).count()
    goals = db_session.query(Goal).limit(10).all()
    goal_items = [{"title": g.title, "progress": round(g.current_value / g.target_value * 100) if g.target_value > 0 else 0} for g in goals]

    try:
        from models import PodOrder
        pod_total = db_session.query(PodOrder).count()
        pod_valid = db_session.query(PodOrder).filter(PodOrder.status_category == "valid").count()
        pod_gmv = db_session.query(func.sum(PodOrder.paid_amount_cny)).filter(PodOrder.status_category == "valid").scalar() or 0
    except Exception:
        pod_total = 0
        pod_valid = 0
        pod_gmv = 0

    return ToolResult(success=True, data={
        "tasks": {"total": total_tasks, "done": done, "pending": pending, "overdue": overdue},
        "employee_count": emp_count,
        "goals": goal_items,
        "pod_orders": {"total": pod_total, "valid": pod_valid, "gmv_cny": round(pod_gmv, 2)},
    })
