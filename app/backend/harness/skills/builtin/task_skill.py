"""Builtin skills for task management."""
from datetime import date
from sqlalchemy import func, case
from harness.skill_registry import tool, ToolResult


@tool(
    name="today_tasks",
    description="获取今日待办任务列表",
    permission_level=0,
)
async def today_tasks(db_session=None, **kwargs) -> ToolResult:
    from models import Task
    tasks = db_session.query(Task).filter(Task.deadline == date.today()).all()
    if not tasks:
        return ToolResult(success=True, data="今日无待办任务。")
    items = [{"title": t.title, "status": t.status.value if hasattr(t.status, 'value') else t.status, "assignee": t.assignee_name or "未指派"} for t in tasks]
    return ToolResult(success=True, data={"count": len(items), "tasks": items})


@tool(
    name="overdue_tasks",
    description="获取当前所有逾期未完成的任务",
    permission_level=0,
)
async def overdue_tasks(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus
    tasks = db_session.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).all()
    if not tasks:
        return ToolResult(success=True, data="当前无逾期任务。")
    items = [{"title": t.title, "assignee": t.assignee_name or "未指派", "deadline": str(t.deadline)} for t in tasks]
    return ToolResult(success=True, data={"count": len(items), "tasks": items})


@tool(
    name="team_progress",
    description="获取团队各成员的任务完成进度",
    permission_level=0,
)
async def team_progress(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus
    results = db_session.query(
        Task.assignee_name,
        func.count(Task.id).label("total"),
        func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)).label("done"),
    ).filter(Task.assignee_name != "").group_by(Task.assignee_name).all()
    if not results:
        return ToolResult(success=True, data="暂无团队任务数据。")
    items = [{"name": r.assignee_name, "total": r.total, "done": r.done, "rate": round(r.done / r.total * 100) if r.total > 0 else 0} for r in results]
    return ToolResult(success=True, data={"members": items})


@tool(
    name="urge_overdue",
    description="对逾期任务发送催办通知",
    parameters={"type": "object", "properties": {}, "required": []},
    permission_level=1,
)
async def urge_overdue(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus
    tasks = db_session.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).all()
    if not tasks:
        return ToolResult(success=True, data="当前无需催办的任务。")
    notified = [{"assignee": t.assignee_name or "未指派", "title": t.title} for t in tasks]
    return ToolResult(success=True, data={"message": "催办通知已发送", "notified": notified})


@tool(
    name="create_task",
    description="创建一个新任务",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "任务标题"},
            "description": {"type": "string", "description": "任务描述"},
            "assignee_name": {"type": "string", "description": "负责人姓名"},
            "deadline": {"type": "string", "description": "截止日期 (YYYY-MM-DD)"},
            "priority": {"type": "string", "enum": ["normal", "high", "urgent"], "description": "优先级"},
        },
        "required": ["title"],
    },
    permission_level=2,
)
async def create_task_skill(db_session=None, **kwargs) -> ToolResult:
    from models import Task
    from datetime import datetime
    task = Task(
        title=kwargs.get("title", ""),
        description=kwargs.get("description", ""),
        assignee_name=kwargs.get("assignee_name", ""),
        priority=kwargs.get("priority", "normal"),
    )
    deadline_str = kwargs.get("deadline")
    if deadline_str:
        try:
            task.deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        except ValueError:
            pass
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return ToolResult(success=True, data={"message": f"任务 '{task.title}' 已创建", "task_id": task.id})
