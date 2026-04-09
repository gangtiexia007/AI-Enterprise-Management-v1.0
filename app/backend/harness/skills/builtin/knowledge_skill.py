"""Builtin skills for knowledge base querying."""
from harness.skill_registry import tool, ToolResult


@tool(
    name="search_knowledge",
    description="搜索知识库（SOP/案例/规则/禁忌），根据关键词匹配标题或内容",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "category": {"type": "string", "enum": ["sop", "case", "rule", "taboo"], "description": "分类过滤（可选）"},
        },
        "required": ["query"],
    },
    permission_level=0,
)
async def search_knowledge(db_session=None, **kwargs) -> ToolResult:
    from models import Knowledge
    query = kwargs.get("query", "")
    q = db_session.query(Knowledge).filter(
        (Knowledge.title.contains(query)) | (Knowledge.content.contains(query))
    )
    category = kwargs.get("category")
    if category:
        q = q.filter(Knowledge.category == category)
    items = q.limit(10).all()
    if not items:
        return ToolResult(success=True, data=f"未找到与 '{query}' 相关的知识。")
    results = [{"id": k.id, "title": k.title, "category": k.category.value if hasattr(k.category, 'value') else k.category, "content_preview": (k.content or "")[:200]} for k in items]
    return ToolResult(success=True, data={"count": len(results), "items": results})
