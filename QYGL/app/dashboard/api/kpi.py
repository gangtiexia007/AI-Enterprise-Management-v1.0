"""P07: KPI management — definitions grouped by team, detail with trend data."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.core.enums import KPIPeriod
from app.dashboard.app import _global_context, get_user_team_filter, render

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("", response_class=HTMLResponse)
async def kpi_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    team_filter = request.query_params.get("team_id", "")
    kpis: list = []
    if user_teams is not None and not user_teams:
        pass
    elif user_teams is not None and team_filter and team_filter not in user_teams:
        pass
    else:
        conditions: dict | None = None
        if team_filter:
            conditions = {"team_id": team_filter}
        elif user_teams is not None:
            conditions = {"team_id": user_teams}
        kpis = db.query("kpi_definitions", conditions, order_by="team_id, name")

    teams = db.query("teams", order_by="name", limit=100)
    if user_teams is not None:
        teams = [t for t in teams if t["id"] in user_teams]

    grouped: dict[str, list] = {}
    team_map = {t["id"]: t.get("name", t["id"]) for t in teams}
    for kpi in kpis:
        tid = kpi.get("team_id", "")
        tname = team_map.get(tid, tid)
        grouped.setdefault(tname, []).append(kpi)

    ctx["grouped_kpis"] = grouped
    ctx["kpis"] = kpis
    ctx["teams"] = teams
    ctx["team_filter"] = team_filter
    ctx["periods"] = [p.value for p in KPIPeriod]
    ctx["stats"] = {
        "total": len(kpis),
        "teams_with_kpi": len(grouped),
    }

    return render(request, "pages/kpi.html", ctx)


@router.get("/scores", response_class=HTMLResponse)
async def kpi_scores_page(request: Request):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    team_id = request.query_params.get("team_id", "").strip()
    employee_id = request.query_params.get("employee_id", "").strip()
    period_key = request.query_params.get("period_key", "").strip()

    sql = """
        SELECT ks.*, kd.name AS kpi_name, kd.team_id AS kpi_team_id,
               e.name AS employee_name
        FROM kpi_scores ks
        JOIN kpi_definitions kd ON ks.kpi_def_id = kd.id
        JOIN employees e ON ks.employee_id = e.id
        WHERE 1=1
    """
    params: list = []
    if user_teams is not None:
        if not user_teams:
            sql += " AND 1=0"
        elif team_id:
            if team_id not in user_teams:
                sql += " AND 1=0"
            else:
                sql += " AND kd.team_id = ?"
                params.append(team_id)
        else:
            ph = ",".join(["?"] * len(user_teams))
            sql += f" AND kd.team_id IN ({ph})"
            params.extend(user_teams)
    elif team_id:
        sql += " AND kd.team_id = ?"
        params.append(team_id)
    if employee_id:
        sql += " AND ks.employee_id = ?"
        params.append(employee_id)
    if period_key:
        sql += " AND ks.period_key = ?"
        params.append(period_key)
    sql += " ORDER BY ks.scored_at DESC LIMIT 500"
    score_rows = db.execute(sql, tuple(params))

    teams = db.query("teams", order_by="name", limit=500)
    if user_teams is not None:
        teams = [t for t in teams if t["id"] in user_teams]
    employees = db.query("employees", order_by="name", limit=2000)
    if user_teams is not None:
        employees = [e for e in employees if e.get("team_id") in user_teams]
    if user_teams is not None and not user_teams:
        kpi_defs: list = []
    else:
        kpi_conds = {"team_id": user_teams} if user_teams is not None else None
        kpi_defs = db.query("kpi_definitions", kpi_conds, order_by="team_id, name", limit=500)

    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in teams}
    for kd in kpi_defs:
        kd["team_label"] = team_map.get(kd.get("team_id", ""), kd.get("team_id", ""))

    ctx = _global_context(request)
    ctx["score_rows"] = score_rows
    ctx["teams"] = teams
    ctx["employees"] = employees
    ctx["kpi_defs"] = kpi_defs
    ctx["team_filter"] = team_id
    ctx["employee_filter"] = employee_id
    ctx["period_filter"] = period_key
    ctx["error"] = request.query_params.get("error", "")
    return render(request, "pages/kpi_scores.html", ctx)


@router.post("/scores")
async def kpi_scores_create_or_update(
    request: Request,
    kpi_def_id: str = Form(...),
    employee_id: str = Form(...),
    period_key: str = Form(...),
    total_score: float = Form(0.0),
    grade: str = Form(...),
    feedback: str = Form(""),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    if user_teams is not None and not user_teams:
        return RedirectResponse("/kpi/scores?error=" + quote("未绑定团队，无法录入"), status_code=302)

    g = (grade or "").strip().upper()
    if g not in ("A", "B", "C", "D"):
        return RedirectResponse(
            "/kpi/scores?error=" + quote("等级须为 A / B / C / D"),
            status_code=302,
        )

    kdef = db.get_by_id("kpi_definitions", kpi_def_id)
    if not kdef:
        return RedirectResponse("/kpi/scores?error=" + quote("KPI 指标无效"), status_code=302)
    if user_teams is not None and kdef.get("team_id") not in user_teams:
        return RedirectResponse("/kpi/scores?error=" + quote("无权操作该 KPI"), status_code=302)

    emp = db.get_by_id("employees", employee_id)
    if not emp:
        return RedirectResponse("/kpi/scores?error=" + quote("员工无效"), status_code=302)
    if user_teams is not None and emp.get("team_id") not in user_teams:
        return RedirectResponse("/kpi/scores?error=" + quote("员工不在您的团队"), status_code=302)

    existing = db.execute(
        "SELECT id FROM kpi_scores WHERE kpi_def_id=? AND employee_id=? AND period_key=?",
        (kpi_def_id, employee_id, period_key),
    )
    now = datetime.utcnow().isoformat()
    if existing:
        db.update(
            "kpi_scores",
            existing[0]["id"],
            {
                "total_score": total_score,
                "grade": g,
                "feedback": feedback or "",
                "scored_at": now,
            },
        )
    else:
        db.insert(
            "kpi_scores",
            {
                "id": new_id(),
                "kpi_def_id": kpi_def_id,
                "employee_id": employee_id,
                "period_key": period_key,
                "total_score": total_score,
                "grade": g,
                "feedback": feedback or "",
                "scored_at": now,
            },
        )
    return RedirectResponse("/kpi/scores", status_code=302)


@router.get("/{kpi_id}", response_class=HTMLResponse)
async def kpi_detail(request: Request, kpi_id: str):
    db = Database.get_instance()
    kpi = db.get_by_id("kpi_definitions", kpi_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and kpi.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="KPI not found")

    ctx = _global_context(request)
    ctx["kpi"] = kpi
    ctx["team"] = db.get_by_id("teams", kpi.get("team_id", ""))

    scores = db.query("kpi_scores", {"kpi_def_id": kpi_id}, order_by="period_key DESC", limit=50)
    ctx["scores"] = scores

    ctx["trend_data"] = {
        "labels": [s.get("period_key", "") for s in reversed(scores)],
        "values": [s.get("total_score", 0) for s in reversed(scores)],
    }

    ctx["data_source_map"] = {
        "source_type": kpi.get("source_type", ""),
        "source_detail": kpi.get("source_detail", ""),
        "update_frequency": kpi.get("update_frequency", ""),
        "responsible_role": kpi.get("responsible_role", ""),
        "dispute_resolver": kpi.get("dispute_resolver", ""),
    }

    ctx["periods"] = [p.value for p in KPIPeriod]

    if request.headers.get("HX-Request"):
        return render(request, "partials/kpi_detail.html", ctx)
    return render(request, "pages/kpi_detail.html", ctx)


@router.post("")
async def create_kpi(
    request: Request,
    name: str = Form(...),
    team_id: str = Form(""),
    period: str = Form("monthly"),
    weight: float = Form(1.0),
    target_value: float = Form(0.0),
    source_type: str = Form(""),
    source_detail: str = Form(""),
    responsible_role: str = Form(""),
    update_frequency: str = Form(""),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    tid = (team_id or "").strip()
    if not tid and user_teams and len(user_teams) == 1:
        tid = user_teams[0]
    if user_teams is not None and tid and tid not in user_teams:
        raise HTTPException(status_code=403, detail="无权为该团队创建 KPI")
    if not tid:
        raise HTTPException(status_code=400, detail="请选择团队")
    db.insert("kpi_definitions", {
        "id": new_id(),
        "name": name,
        "team_id": tid,
        "period": period,
        "weight": weight,
        "target_value": target_value,
        "source_type": source_type,
        "source_detail": source_detail,
        "responsible_role": responsible_role,
        "update_frequency": update_frequency,
    })
    return RedirectResponse("/kpi", status_code=302)


@router.post("/{kpi_id}/update")
async def update_kpi(
    request: Request,
    kpi_id: str,
    name: str = Form(...),
    period: str = Form("monthly"),
    target_value: float = Form(0.0),
    weight: float = Form(1.0),
    source_type: str = Form(""),
    source_detail: str = Form(""),
    update_frequency: str = Form(""),
    responsible_role: str = Form(""),
    dispute_resolver: str = Form(""),
    scoring_json: str = Form("{}"),
    metrics_json: str = Form("{}"),
):
    db = Database.get_instance()
    kpi = db.get_by_id("kpi_definitions", kpi_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and kpi.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="KPI not found")
    db.update(
        "kpi_definitions",
        kpi_id,
        {
            "name": name,
            "period": period,
            "target_value": target_value,
            "weight": weight,
            "source_type": source_type,
            "source_detail": source_detail,
            "update_frequency": update_frequency,
            "responsible_role": responsible_role,
            "dispute_resolver": dispute_resolver,
            "scoring_json": scoring_json or "{}",
            "metrics_json": metrics_json or "{}",
        },
    )
    return RedirectResponse(f"/kpi/{kpi_id}", status_code=302)


@router.post("/{kpi_id}/delete")
async def delete_kpi(request: Request, kpi_id: str):
    db = Database.get_instance()
    kpi = db.get_by_id("kpi_definitions", kpi_id)
    if not kpi:
        raise HTTPException(status_code=404, detail="KPI not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and kpi.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="KPI not found")
    db.execute("DELETE FROM kpi_scores WHERE kpi_def_id=?", (kpi_id,))
    db.delete("kpi_definitions", kpi_id)
    return RedirectResponse("/kpi", status_code=302)
