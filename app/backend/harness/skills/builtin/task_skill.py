"""Builtin skills for task management — enhanced with goal decomposition and Feishu dispatch."""
from datetime import date, datetime
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
    description="对逾期任务发送催办通知（通过飞书）",
    parameters={"type": "object", "properties": {}, "required": []},
    permission_level=1,
)
async def urge_overdue(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus, Employee
    from harness.feishu_client import feishu_client

    tasks = db_session.query(Task).filter(
        Task.deadline < date.today(),
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED])
    ).all()
    if not tasks:
        return ToolResult(success=True, data="当前无需催办的任务。")

    notified = []
    for t in tasks:
        days = (date.today() - t.deadline).days if t.deadline else 0
        entry = {"assignee": t.assignee_name or "未指派", "title": t.title, "days_overdue": days, "feishu_sent": False}

        if t.assignee_id:
            emp = db_session.query(Employee).filter(Employee.id == t.assignee_id).first()
            if emp and emp.feishu_id:
                ok = feishu_client.send_reminder(emp.feishu_id, t.title, days, assignee=emp.name)
                entry["feishu_sent"] = ok

        notified.append(entry)

    return ToolResult(success=True, data={"message": "催办通知已发送", "count": len(notified), "notified": notified})


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
            "goal_id": {"type": "integer", "description": "关联目标ID（可选）"},
        },
        "required": ["title"],
    },
    permission_level=2,
)
async def create_task_skill(db_session=None, **kwargs) -> ToolResult:
    from models import Task, Employee
    from harness.feishu_client import feishu_client

    assignee_name = kwargs.get("assignee_name", "")
    emp = None
    if assignee_name:
        emp = db_session.query(Employee).filter(Employee.name.contains(assignee_name)).first()

    task = Task(
        title=kwargs.get("title", ""),
        description=kwargs.get("description", ""),
        assignee_name=emp.name if emp else assignee_name,
        assignee_id=emp.id if emp else None,
        priority=kwargs.get("priority", "normal"),
        goal_id=kwargs.get("goal_id"),
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

    feishu_sent = False
    if emp and emp.feishu_id:
        feishu_sent = feishu_client.send_task_notification(
            emp.feishu_id,
            task.title,
            description=task.description,
            deadline=str(task.deadline) if task.deadline else "",
            assignee=emp.name,
        )

    return ToolResult(success=True, data={
        "message": f"任务 '{task.title}' 已创建",
        "task_id": task.id,
        "feishu_notified": feishu_sent,
    })


@tool(
    name="decompose_goal",
    description="将目标拆解为多个可执行的子任务（AI辅助拆解），自动创建任务并分配",
    parameters={
        "type": "object",
        "properties": {
            "goal_id": {"type": "integer", "description": "目标ID"},
            "num_tasks": {"type": "integer", "description": "拆解为几个任务（默认3-5个）"},
        },
        "required": ["goal_id"],
    },
    permission_level=2,
)
async def decompose_goal(db_session=None, **kwargs) -> ToolResult:
    from models import Goal, Task, Employee
    import json

    goal_id = kwargs.get("goal_id")
    goal = db_session.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        return ToolResult(success=False, error=f"目标 ID {goal_id} 不存在")

    num_tasks = kwargs.get("num_tasks", 4)
    employees = db_session.query(Employee).all()
    emp_names = [e.name for e in employees] if employees else ["未指派"]

    try:
        from harness.ai_client import ai_client
        prompt = f"""请将以下目标拆解为 {num_tasks} 个具体可执行的任务。

目标: {goal.title}
目标值: {goal.target_value} {goal.unit}
截止日期: {goal.deadline or '未设置'}
可分配人员: {', '.join(emp_names)}

请用JSON数组返回，每个元素包含:
- title: 任务标题
- description: 简要描述
- assignee_name: 负责人（从可分配人员中选择）
- deadline: 截止日期 (YYYY-MM-DD)
- priority: normal/high/urgent

只返回JSON数组，不要其他内容。"""

        response = await ai_client.chat(
            [{"role": "system", "content": "你是任务拆解助手，将目标分解为可执行任务。只返回JSON。"},
             {"role": "user", "content": prompt}],
            max_tokens=1000,
        )

        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            task_defs = json.loads(response[start:end])
        else:
            return ToolResult(success=False, error="AI 拆解失败，请手动创建任务")

    except Exception as e:
        return ToolResult(success=False, error=f"AI 拆解失败: {str(e)}")

    created_tasks = []
    for td in task_defs[:num_tasks + 2]:
        if not isinstance(td, dict) or not td.get("title"):
            continue

        assignee = td.get("assignee_name", "")
        emp = db_session.query(Employee).filter(Employee.name == assignee).first() if assignee else None

        task = Task(
            title=td["title"],
            description=td.get("description", ""),
            assignee_name=emp.name if emp else assignee,
            assignee_id=emp.id if emp else None,
            priority=td.get("priority", "normal"),
            goal_id=goal.id,
        )
        dl = td.get("deadline")
        if dl:
            try:
                task.deadline = datetime.strptime(dl, "%Y-%m-%d").date()
            except ValueError:
                pass

        db_session.add(task)
        created_tasks.append(td["title"])

    db_session.commit()
    return ToolResult(success=True, data={
        "message": f"目标「{goal.title}」已拆解为 {len(created_tasks)} 个任务",
        "tasks": created_tasks,
    })
