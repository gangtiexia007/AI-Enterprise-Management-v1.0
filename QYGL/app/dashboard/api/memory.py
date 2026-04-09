"""P11: Memory management — layer tabs L1-L5, detail with audit metadata."""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.core.database import Database
from app.core.enums import MemoryLayer
from app.dashboard.app import templates, _global_context, render

router = APIRouter(prefix="/memory", tags=["memory"])

LAYER_DESCRIPTIONS = {
    "L1": "系统规则 — 硬约束",
    "L2": "团队 SOP — 操作规程",
    "L3": "员工档案 — 行为画像",
    "L4": "业务知识 — 案例库",
    "L5": "对话记忆 — 会话摘要",
}


@router.get("", response_class=HTMLResponse)
async def memory_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    layer = request.query_params.get("layer", "")
    team_id = request.query_params.get("team_id", "")

    conditions: dict = {}
    if layer:
        conditions["layer"] = layer
    if team_id:
        conditions["team_id"] = team_id

    memories = db.query("memories", conditions or None, order_by="created_at DESC", limit=200)

    layer_counts = {}
    for lyr in MemoryLayer:
        layer_counts[lyr.value] = db.count("memories", {"layer": lyr.value})

    ctx["memories"] = memories
    ctx["layer_filter"] = layer
    ctx["team_filter"] = team_id
    ctx["layers"] = [l.value for l in MemoryLayer]
    ctx["layer_descriptions"] = LAYER_DESCRIPTIONS
    ctx["layer_counts"] = layer_counts
    ctx["teams"] = db.query("teams", order_by="name", limit=100)
    ctx["stats"] = {
        "total": sum(layer_counts.values()),
        "verified": sum(1 for m in memories if m.get("is_verified")),
    }

    return render(request, "pages/memory.html", ctx)


@router.get("/{memory_id}", response_class=HTMLResponse)
async def memory_detail(request: Request, memory_id: str):
    db = Database.get_instance()
    memory = db.get_by_id("memories", memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    ctx = _global_context(request)
    ctx["memory"] = memory
    ctx["layer_desc"] = LAYER_DESCRIPTIONS.get(memory.get("layer", ""), "")

    import json
    meta_raw = memory.get("metadata_json", "{}")
    if isinstance(meta_raw, str):
        try:
            ctx["metadata"] = json.loads(meta_raw)
        except json.JSONDecodeError:
            ctx["metadata"] = {}
    else:
        ctx["metadata"] = meta_raw

    if request.headers.get("HX-Request"):
        return render(request, "partials/memory_detail.html", ctx)
    return render(request, "pages/memory_detail.html", ctx)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    db = Database.get_instance()
    memory = db.get_by_id("memories", memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete("memories", memory_id)
    return JSONResponse({"ok": True})


@router.post("/{memory_id}/delete")
async def delete_memory_form(memory_id: str):
    db = Database.get_instance()
    db.delete("memories", memory_id)
    return RedirectResponse("/memory", status_code=302)
