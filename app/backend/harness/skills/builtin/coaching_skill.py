"""Builtin skills for coaching and employee development."""
from harness.skill_registry import tool, ToolResult


@tool(
    name="coaching_suggestions",
    description="为指定员工生成 AI 辅导建议（基于 KPI 和任务完成情况）",
    parameters={
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "员工姓名（可选，不填则分析全部）"},
        },
        "required": [],
    },
    permission_level=0,
)
async def coaching_suggestions(db_session=None, **kwargs) -> ToolResult:
    from models import Employee, KPIRecord, Task, TaskStatus, CoachingRecord
    from sqlalchemy import func
    from datetime import date

    emp_name = kwargs.get("employee_name", "")

    q = db_session.query(
        KPIRecord.employee_id,
        KPIRecord.employee_name,
        func.avg(KPIRecord.score).label("avg_score"),
        func.count(KPIRecord.id).label("count"),
    ).group_by(KPIRecord.employee_id, KPIRecord.employee_name)

    if emp_name:
        q = q.filter(KPIRecord.employee_name.contains(emp_name))

    results = q.all()
    if not results:
        return ToolResult(success=True, data="暂无 KPI 数据可供分析。")

    suggestions = []
    for emp_id, name, avg_score, count in results:
        overdue_count = db_session.query(Task).filter(
            Task.assignee_name == name,
            Task.status == TaskStatus.OVERDUE,
        ).count()

        total_tasks = db_session.query(Task).filter(Task.assignee_name == name).count()
        done_tasks = db_session.query(Task).filter(Task.assignee_name == name, Task.status == TaskStatus.DONE).count()
        completion_rate = round(done_tasks / total_tasks * 100) if total_tasks > 0 else 0

        strength = "执行力强" if completion_rate > 80 else "需提升执行力"
        if avg_score >= 100:
            strength = "绩效优秀"

        suggestion = {
            "employee": name,
            "avg_kpi": round(avg_score, 1),
            "completion_rate": completion_rate,
            "overdue_tasks": overdue_count,
            "strength": strength,
            "advice": [],
        }

        if avg_score < 60:
            suggestion["advice"].append("KPI 得分偏低，建议一对一沟通了解困难，制定改进计划")
        if overdue_count > 0:
            suggestion["advice"].append(f"有 {overdue_count} 个逾期任务，建议协助梳理优先级")
        if completion_rate < 50:
            suggestion["advice"].append("任务完成率不足50%，建议拆分大任务为小步骤")
        if not suggestion["advice"]:
            suggestion["advice"].append("保持当前表现，可考虑承担更多挑战性项目")

        suggestions.append(suggestion)

    return ToolResult(success=True, data={"employees": suggestions})


@tool(
    name="employee_score",
    description="查询指定员工的综合评分（KPI + 任务完成率）",
    parameters={
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "员工姓名"},
        },
        "required": ["employee_name"],
    },
    permission_level=0,
)
async def employee_score(db_session=None, **kwargs) -> ToolResult:
    from models import KPIRecord, Task, TaskStatus
    from sqlalchemy import func

    name = kwargs.get("employee_name", "")
    if not name:
        return ToolResult(success=False, error="请指定员工姓名")

    kpi_avg = db_session.query(func.avg(KPIRecord.score)).filter(
        KPIRecord.employee_name.contains(name),
    ).scalar()

    total = db_session.query(Task).filter(Task.assignee_name.contains(name)).count()
    done = db_session.query(Task).filter(Task.assignee_name.contains(name), Task.status == TaskStatus.DONE).count()
    overdue = db_session.query(Task).filter(Task.assignee_name.contains(name), Task.status == TaskStatus.OVERDUE).count()

    kpi_score = round(kpi_avg, 1) if kpi_avg else 0
    completion = round(done / total * 100) if total > 0 else 0

    return ToolResult(success=True, data={
        "employee": name,
        "kpi_avg_score": kpi_score,
        "total_tasks": total,
        "completed": done,
        "overdue": overdue,
        "completion_rate": completion,
    })


@tool(
    name="weekly_data",
    description="获取本周关键业务数据摘要",
    permission_level=0,
)
async def weekly_data(db_session=None, **kwargs) -> ToolResult:
    from models import Task, TaskStatus, Goal, KPIRecord
    from sqlalchemy import func
    from datetime import date, timedelta

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    new_tasks = db_session.query(Task).filter(Task.created_at >= week_start.isoformat()).count()
    done_tasks = db_session.query(Task).filter(
        Task.status == TaskStatus.DONE,
        Task.updated_at >= week_start.isoformat(),
    ).count()
    overdue = db_session.query(Task).filter(
        Task.deadline < today,
        Task.status.notin_([TaskStatus.DONE, TaskStatus.FEEDBACK_SUBMITTED]),
    ).count()

    goals = db_session.query(Goal).filter(Goal.target_value > 0).all()
    goal_pct = 0
    if goals:
        goal_pct = round(sum(g.current_value / g.target_value for g in goals) / len(goals) * 100)

    avg_kpi = db_session.query(func.avg(KPIRecord.score)).scalar()

    return ToolResult(success=True, data={
        "week": f"{week_start} ~ {today}",
        "new_tasks": new_tasks,
        "completed_tasks": done_tasks,
        "overdue_tasks": overdue,
        "goal_progress_avg": goal_pct,
        "kpi_avg": round(avg_kpi, 1) if avg_kpi else 0,
    })
