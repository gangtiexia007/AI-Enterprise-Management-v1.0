"""F41: Decision log — list, detail, manual creation."""

from __future__ import annotations

import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database
from app.core.enums import ReviewStatus
from app.dashboard.app import _global_context, get_user_team_filter, render

logger = logging.getLogger(__name__)

router = APIRouter(tags=["decisions"])


@router.get("/decisions", response_class=HTMLResponse)
async def decisions_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    team_id = request.query_params.get("team_id", "")
    status = request.query_params.get("status", "")

    conditions: dict = {}
    if status:
        conditions["review_status"] = status

    decisions: list = []

    if user_teams is not None and not user_teams:
        pass
    elif user_teams is not None and team_id and team_id not in user_teams:
        pass
    else:
        if user_teams is not None:
            conditions["team_id"] = team_id if team_id else user_teams
        elif team_id:
            conditions["team_id"] = team_id
        decisions = db.query(
            "decision_logs", conditions or None, order_by="created_at DESC", limit=200
        )

    teams = db.query("teams", order_by="name", limit=100)
    if user_teams is not None:
        teams = [t for t in teams if t["id"] in user_teams]

    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in teams}

    emp_ids = {d.get("employee_id") for d in decisions if d.get("employee_id")}
    employee_map: dict[str, str] = {}
    for eid in emp_ids:
        emp = db.get_by_id("employees", eid)
        if emp:
            employee_map[eid] = emp.get("name") or eid

    ctx.update(
        {
            "decisions": decisions,
            "teams": teams,
            "team_map": team_map,
            "employee_map": employee_map,
            "team_filter": team_id,
            "status_filter": status,
            "review_statuses": [s.value for s in ReviewStatus],
            "stats": {
                "total": len(decisions),
                "pending": sum(
                    1 for d in decisions if d.get("review_status") == "pending"
                ),
                "reviewed": sum(
                    1 for d in decisions if d.get("review_status") == "reviewed"
                ),
            },
        }
    )

    return render(request, "pages/decisions.html", ctx)


@router.get("/decisions/{decision_id}", response_class=HTMLResponse)
async def decision_detail(request: Request, decision_id: str):
    db = Database.get_instance()
    decision = db.get_by_id("decision_logs", decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    user_teams = get_user_team_filter(request)
    if user_teams is not None and decision.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Decision not found")

    ctx = _global_context(request)

    teams = db.query("teams", order_by="name", limit=100)
    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in teams}

    employee = None
    if decision.get("employee_id"):
        employee = db.get_by_id("employees", decision["employee_id"])

    decision = dict(decision)
    for json_field in ("tracked_metrics_json", "metric_snapshot_before", "metric_snapshot_after"):
        raw = decision.get(json_field, "{}")
        if isinstance(raw, str):
            try:
                decision[json_field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                decision[json_field] = {}

    evaluation: dict = {}
    if decision.get("evaluation"):
        try:
            evaluation = (
                json.loads(decision["evaluation"])
                if isinstance(decision["evaluation"], str)
                else decision["evaluation"]
            )
        except (json.JSONDecodeError, TypeError):
            evaluation = {}

    ctx.update(
        {
            "decision": decision,
            "employee": employee,
            "team_map": team_map,
            "evaluation": evaluation,
        }
    )

    return render(request, "pages/decision_detail.html", ctx)


@router.post("/decisions")
async def create_decision(
    request: Request,
    team_id: str = Form(...),
    employee_id: str = Form(""),
    decision: str = Form(...),
    data_basis: str = Form(""),
    expected_result: str = Form(""),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    if user_teams is not None and team_id not in user_teams:
        raise HTTPException(status_code=403, detail="无权为该团队创建决策记录")

    from app.engines.decision import DecisionEngine

    engine = DecisionEngine(db=db)
    engine.record_decision(
        team_id=team_id,
        employee_id=employee_id,
        decision=decision,
        data_basis=data_basis,
        expected_result=expected_result,
    )

    return RedirectResponse("/decisions?msg=" + quote("决策记录创建成功"), status_code=302)
