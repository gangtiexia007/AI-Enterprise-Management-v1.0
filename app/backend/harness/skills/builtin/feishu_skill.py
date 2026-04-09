"""Builtin skills for Feishu integration."""
from harness.skill_registry import tool, ToolResult


@tool(
    name="send_feishu_message",
    description="通过飞书发送消息给指定员工",
    parameters={
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "员工姓名"},
            "message": {"type": "string", "description": "消息内容"},
        },
        "required": ["employee_name", "message"],
    },
    permission_level=1,
)
async def send_feishu_message(db_session=None, **kwargs) -> ToolResult:
    from models import Employee
    from harness.feishu_client import feishu_client

    name = kwargs.get("employee_name", "")
    message = kwargs.get("message", "")

    emp = db_session.query(Employee).filter(Employee.name.contains(name)).first()
    if not emp:
        return ToolResult(success=False, error=f"未找到员工: {name}")
    if not emp.feishu_id:
        return ToolResult(success=False, error=f"员工 {name} 未配置飞书 ID")

    ok = feishu_client.send_text_message(emp.feishu_id, message)
    return ToolResult(success=True, data={"sent": ok, "employee": emp.name, "feishu_id": emp.feishu_id})


@tool(
    name="notify_task_to_feishu",
    description="将任务通知发送到负责人的飞书",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "integer", "description": "任务ID"},
        },
        "required": ["task_id"],
    },
    permission_level=1,
)
async def notify_task_to_feishu(db_session=None, **kwargs) -> ToolResult:
    from models import Task, Employee
    from harness.feishu_client import feishu_client

    task_id = kwargs.get("task_id")
    task = db_session.query(Task).filter(Task.id == task_id).first()
    if not task:
        return ToolResult(success=False, error=f"任务 ID {task_id} 不存在")

    emp = None
    if task.assignee_id:
        emp = db_session.query(Employee).filter(Employee.id == task.assignee_id).first()

    if not emp or not emp.feishu_id:
        return ToolResult(success=True, data={"sent": False, "reason": "负责人未配置飞书ID"})

    deadline_str = str(task.deadline) if task.deadline else "未设置"
    ok = feishu_client.send_task_notification(
        emp.feishu_id,
        task.title,
        description=task.description or "",
        deadline=deadline_str,
        assignee=emp.name,
    )
    return ToolResult(success=True, data={"sent": ok, "employee": emp.name})


@tool(
    name="push_daily_report",
    description="立即推送每日管理简报到老板飞书",
    permission_level=1,
)
async def push_daily_report(db_session=None, **kwargs) -> ToolResult:
    from harness.feishu_client import feishu_client
    from models import Setting

    boss_id_setting = db_session.query(Setting).filter(Setting.key == "feishu_boss_id").first()
    boss_id = boss_id_setting.value if boss_id_setting else ""
    if not boss_id:
        return ToolResult(success=False, error="未配置老板飞书ID (feishu_boss_id)")

    from harness.skills.builtin.report_skill import daily_report
    report_result = await daily_report(db_session=db_session)
    if not report_result.success:
        return report_result

    import json
    report_data = report_result.data
    if isinstance(report_data, str):
        text = report_data
    else:
        text = json.dumps(report_data, ensure_ascii=False, indent=2)

    ok = feishu_client.send_daily_report(boss_id, text)
    return ToolResult(success=True, data={"pushed": ok, "boss_id": boss_id})


@tool(
    name="collect_feedback",
    description="记录员工通过飞书提交的任务反馈",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "integer", "description": "任务ID"},
            "employee_name": {"type": "string", "description": "员工姓名"},
            "content": {"type": "string", "description": "反馈内容"},
        },
        "required": ["task_id", "content"],
    },
    permission_level=1,
)
async def collect_feedback(db_session=None, **kwargs) -> ToolResult:
    from models import Task, Feedback, Employee, TaskStatus
    from datetime import datetime

    task_id = kwargs.get("task_id")
    task = db_session.query(Task).filter(Task.id == task_id).first()
    if not task:
        return ToolResult(success=False, error=f"任务 ID {task_id} 不存在")

    emp_name = kwargs.get("employee_name", "")
    emp = db_session.query(Employee).filter(Employee.name.contains(emp_name)).first() if emp_name else None

    feedback = Feedback(
        task_id=task_id,
        employee_id=emp.id if emp else None,
        content=kwargs.get("content", ""),
        submitted_at=datetime.utcnow(),
    )
    db_session.add(feedback)
    task.status = TaskStatus.FEEDBACK_SUBMITTED
    task.updated_at = datetime.utcnow()
    db_session.commit()

    return ToolResult(success=True, data={"message": f"反馈已记录 (任务: {task.title})", "feedback_id": feedback.id})
