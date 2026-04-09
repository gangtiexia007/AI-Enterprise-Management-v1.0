"""P08: Escalation management — list sorted by urgency, task timeline."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse

from app.core.database import Database
from app.core.enums import EscalationLevel
from app.dashboard.app import _global_context, get_user_team_filter, render

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_class=HTMLResponse)
async def escalation_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    level_filter = request.query_params.get("level", "")
    conditions: dict | None = {"level": level_filter} if level_filter else {}

    if user_teams is not None:
        if not user_teams:
            conditions = None
            escalations = []
            task_ids: list = []
        else:
            team_tasks = db.query("tasks", {"team_id": user_teams}, limit=5000)
            allowed_task_ids = {t["id"] for t in team_tasks}
            base = db.query("escalations", conditions if conditions else None, order_by="sent_at DESC", limit=500)
            escalations = [e for e in base if e.get("task_id") in allowed_task_ids][:200]
            task_ids = list({e.get("task_id", "") for e in escalations if e.get("task_id")})
    else:
        conditions = {"level": level_filter} if level_filter else None
        escalations = db.query("escalations", conditions, order_by="sent_at DESC", limit=200)
        task_ids = list({e.get("task_id", "") for e in escalations if e.get("task_id")})
    tasks_map = {}
    for tid in task_ids:
        t = db.get_by_id("tasks", tid)
        if t:
            tasks_map[tid] = t

    for esc in escalations:
        esc["task"] = tasks_map.get(esc.get("task_id", ""))

    level_order = {EscalationLevel.BOSS: 0, "boss": 0, EscalationLevel.MANAGER: 1, "manager": 1, EscalationLevel.EMPLOYEE: 2, "employee": 2}
    escalations.sort(key=lambda e: level_order.get(e.get("level", ""), 99))

    ctx["escalations"] = escalations
    ctx["level_filter"] = level_filter
    ctx["levels"] = [l.value for l in EscalationLevel]
    ctx["stats"] = {
        "total": len(escalations),
        "boss_level": sum(1 for e in escalations if e.get("level") == "boss"),
        "unresolved": sum(1 for e in escalations if not e.get("response_at")),
    }

    return render(request, "pages/escalation.html", ctx)


@router.post("/{escalation_id}/respond")
async def respond_escalation(request: Request, escalation_id: str):
    db = Database.get_instance()
    esc = db.get_by_id("escalations", escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    task = db.get_by_id("tasks", esc.get("task_id", ""))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Escalation not found")
    response_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.update("escalations", escalation_id, {"response_at": response_at})
    task_id = esc.get("task_id", "")
    return RedirectResponse(f"/escalations/{task_id}", status_code=302)


@router.get("/{task_id}", response_class=HTMLResponse)
async def escalation_timeline(request: Request, task_id: str):
    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")

    timeline = db.query("escalations", {"task_id": task_id}, order_by="sent_at ASC")

    ctx = _global_context(request)
    ctx["task"] = task
    ctx["timeline"] = timeline
    ctx["team"] = db.get_by_id("teams", task.get("team_id", ""))

    if request.headers.get("HX-Request"):
        return render(request, "partials/escalation_timeline.html", ctx)
    return render(request, "pages/escalation_detail.html", ctx)
