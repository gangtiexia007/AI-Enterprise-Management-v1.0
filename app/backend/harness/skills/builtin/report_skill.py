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
    return ToolResult(success=True, data={
        "date": str(date.today()),
        "total_tasks": total,
        "done_today": done_today,
        "overdue": overdue,
        "pending": pending,
        "goal_progress": goal_progress,
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
    return ToolResult(success=True, data={
        "tasks": {"total": total_tasks, "done": done, "pending": pending, "overdue": overdue},
        "employee_count": emp_count,
        "goals": goal_items,
    })
