"""Builtin skills for goal management."""
from harness.skill_registry import tool, ToolResult


@tool(
    name="list_goals",
    description="列出当前所有目标及其达成进度",
    permission_level=0,
)
async def list_goals(db_session=None, **kwargs) -> ToolResult:
    from models import Goal
    goals = db_session.query(Goal).all()
    if not goals:
        return ToolResult(success=True, data="暂无目标数据。")
    items = [{
        "id": g.id,
        "title": g.title,
        "level": g.level.value if hasattr(g.level, 'value') else g.level,
        "owner": g.owner,
        "progress": round(g.current_value / g.target_value * 100) if g.target_value > 0 else 0,
        "target": g.target_value,
        "current": g.current_value,
        "unit": g.unit,
    } for g in goals]
    return ToolResult(success=True, data={"count": len(items), "goals": items})


@tool(
    name="update_goal_progress",
    description="更新目标的当前进度值",
    parameters={
        "type": "object",
        "properties": {
            "goal_id": {"type": "integer", "description": "目标ID"},
            "current_value": {"type": "number", "description": "新的当前值"},
        },
        "required": ["goal_id", "current_value"],
    },
    permission_level=2,
)
async def update_goal_progress(db_session=None, **kwargs) -> ToolResult:
    from models import Goal
    goal_id = kwargs.get("goal_id")
    new_value = kwargs.get("current_value")
    goal = db_session.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        return ToolResult(success=False, error=f"目标 ID {goal_id} 不存在")
    goal.current_value = new_value
    db_session.commit()
    progress = round(goal.current_value / goal.target_value * 100) if goal.target_value > 0 else 0
    return ToolResult(success=True, data={"message": f"目标 '{goal.title}' 进度已更新至 {progress}%"})
