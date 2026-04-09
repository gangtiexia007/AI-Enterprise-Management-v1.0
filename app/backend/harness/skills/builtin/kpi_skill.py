"""Builtin skills for KPI management."""
from harness.skill_registry import tool, ToolResult


@tool(
    name="kpi_summary",
    description="获取各员工的 KPI 绩效摘要（平均分和等级）",
    permission_level=0,
)
async def kpi_summary(db_session=None, **kwargs) -> ToolResult:
    from sqlalchemy import func
    from models import KPIRecord
    results = db_session.query(
        KPIRecord.employee_name,
        func.avg(KPIRecord.score).label("avg_score"),
        func.count(KPIRecord.id).label("count"),
    ).group_by(KPIRecord.employee_name).all()
    if not results:
        return ToolResult(success=True, data="暂无 KPI 数据。")
    items = [{"name": r.employee_name, "avg_score": round(r.avg_score, 1), "records": r.count} for r in results]
    return ToolResult(success=True, data={"employees": items})


@tool(
    name="calculate_kpi",
    description="触发 KPI 得分重新计算",
    permission_level=1,
)
async def calculate_kpi(db_session=None, **kwargs) -> ToolResult:
    from harness.rules_engine import calculate_kpi_scores
    updated = calculate_kpi_scores(db_session)
    return ToolResult(success=True, data={"message": f"已重新计算 {updated} 条 KPI 记录"})
