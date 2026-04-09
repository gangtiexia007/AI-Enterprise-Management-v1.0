"""P02 + P03: Team management — list, detail (11 tabs), CRUD, bot test."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import RedirectResponse

from app.core.database import Database, new_id
from app.core.enums import TeamStatus
from app.core.team_registry import TeamRegistry
from app.core.exceptions import TeamNotFound, ValidationError
from app.dashboard.app import templates, _global_context, render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_class=HTMLResponse)
async def team_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    status_filter = request.query_params.get("status", "")
    filters = {"status": status_filter} if status_filter else None

    registry = TeamRegistry(db)
    teams = registry.list_teams(filters)

    for team in teams:
        team["employee_count"] = db.count("employees", {"team_id": team["id"]})
        bots = db.query("team_bots", {"team_id": team["id"]})
        team["bots"] = bots
        team["bot_connected"] = any(b.get("verified") for b in bots)

    ctx["teams"] = teams
    ctx["status_filter"] = status_filter
    ctx["statuses"] = [s.value for s in TeamStatus]
    return render(request, "pages/team_list.html", ctx)


@router.get("/{team_id}", response_class=HTMLResponse)
async def team_detail_page(request: Request, team_id: str):
    db = Database.get_instance()
    ctx = _global_context(request)

    registry = TeamRegistry(db)
    try:
        team = registry.get_team_config(team_id)
    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Team not found")

    ctx["team"] = team
    ctx["employees"] = db.query("employees", {"team_id": team_id}, order_by="name")
    ctx["sub_agents"] = db.query("sub_agents", {"team_id": team_id}, order_by="sort_order")
    ctx["skills"] = db.query("skills", limit=100)
    ctx["team_skills"] = db.query("team_skills", {"team_id": team_id})
    ctx["kpi_definitions"] = db.query("kpi_definitions", {"team_id": team_id})
    ctx["models"] = db.query("models", {"enabled": True})
    ctx["knowledge_items"] = db.query("knowledge", limit=50)
    ctx["report_templates"] = db.query(
        "report_templates", {"team_id": team_id}, order_by="created_at DESC", limit=100
    )
    ctx["tab"] = request.query_params.get("tab", "basic")
    ctx["report_types"] = ("daily", "weekly", "monthly")

    return render(request, "pages/team_detail.html", ctx)


@router.post("/{team_id}/report-template")
async def create_report_template(
    team_id: str,
    name: str = Form(...),
    template_content: str = Form(""),
    report_type: str = Form("daily"),
):
    db = Database.get_instance()
    if not db.get_by_id("teams", team_id):
        raise HTTPException(status_code=404, detail="Team not found")
    rt = (report_type or "daily").strip()
    if rt not in ("daily", "weekly", "monthly"):
        rt = "daily"
    db.insert("report_templates", {
        "id": new_id(),
        "team_id": team_id,
        "name": name.strip(),
        "template_content": template_content or "",
        "report_type": rt,
    })
    return RedirectResponse(f"/teams/{team_id}?tab=reports", status_code=302)


@router.post("", response_class=HTMLResponse)
async def create_team(
    request: Request,
    name: str = Form(...),
    department: str = Form(""),
    automation_profile: str = Form("startup"),
    system_prompt: str = Form(""),
):
    registry = TeamRegistry()
    try:
        team = registry.create_team({
            "name": name,
            "department": department,
            "automation_profile": automation_profile,
            "system_prompt": system_prompt,
        })
        return RedirectResponse(f"/teams/{team['id']}", status_code=302)
    except ValidationError as e:
        ctx = _global_context(request)
        ctx["error"] = str(e)
        ctx["teams"] = registry.list_teams()
        return render(request, "pages/team_list.html", ctx, status_code=400)


@router.put("/{team_id}")
async def update_team(request: Request, team_id: str):
    registry = TeamRegistry()
    body = await request.json()
    try:
        team = registry.update_team(team_id, body)
        return JSONResponse({"ok": True, "team": team})
    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Team not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{team_id}/update")
async def update_team_form(request: Request, team_id: str):
    """Handle form-based team updates from the detail page."""
    form = await request.form()
    data = {}
    for key in ("name", "display_name", "department", "system_prompt",
                "primary_model", "fallback_model", "automation_profile", "status"):
        val = form.get(key)
        if val is not None:
            data[key] = val

    for json_field in ("data_scope_json", "knowledge_scope_json", "escalation_json"):
        raw = form.get(json_field)
        if raw:
            try:
                data[json_field] = json.loads(raw)
            except json.JSONDecodeError:
                pass

    registry = TeamRegistry()
    registry.update_team(team_id, data)
    return RedirectResponse(f"/teams/{team_id}?tab={form.get('tab', 'basic')}", status_code=302)


@router.post("/{team_id}/publish")
async def publish_team(team_id: str):
    db = Database.get_instance()
    team = db.get_by_id("teams", team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db.update("teams", team_id, {"status": "active"})
    return RedirectResponse(f"/teams/{team_id}", status_code=302)


@router.delete("/{team_id}")
async def delete_team(team_id: str):
    registry = TeamRegistry()
    try:
        registry.delete_team(team_id)
        return JSONResponse({"ok": True})
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TeamNotFound:
        raise HTTPException(status_code=404, detail="Team not found")


@router.post("/{team_id}/delete")
async def delete_team_form(team_id: str):
    registry = TeamRegistry()
    try:
        registry.delete_team(team_id)
        return RedirectResponse("/teams", status_code=302)
    except ValidationError as e:
        return RedirectResponse(f"/teams/{team_id}?error={e.message}", status_code=302)


@router.post("/{team_id}/test-bot")
async def test_bot_connection(team_id: str):
    db = Database.get_instance()
    bots = db.query("team_bots", {"team_id": team_id})
    results = []
    for bot in bots:
        connected = bool(bot.get("app_id_encrypted") and bot.get("webhook_url"))
        if connected:
            db.update("team_bots", bot["id"], {"verified": True})
        results.append({
            "id": bot["id"],
            "channel": bot.get("channel"),
            "connected": connected,
        })
    return JSONResponse({"ok": True, "results": results})
