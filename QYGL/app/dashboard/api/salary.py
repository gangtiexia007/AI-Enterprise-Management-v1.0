"""Dashboard: salary / reward calculation overview and batch trigger."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.core.enums import RewardStatus
from app.core.exceptions import ValidationError
from app.dashboard.app import _global_context, render
from app.engines.calc import CalcEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/salary", tags=["salary"])


def _team_display_map(db: Database) -> dict[str, str]:
    teams = db.query("teams", order_by="name", limit=500)
    return {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in teams}


@router.get("", response_class=HTMLResponse)
async def salary_page(request: Request):
    db = Database.get_instance()
    team_filter = request.query_params.get("team_id", "").strip()
    period_filter = request.query_params.get("period", "").strip()
    status_filter = request.query_params.get("status", "").strip()

    sql = """
        SELECT rc.*, e.name AS employee_name, rr.name AS rule_name, ks.grade AS kpi_grade
        FROM reward_calculations rc
        JOIN employees e ON rc.employee_id = e.id
        LEFT JOIN reward_rules rr ON rc.rule_id = rr.id
        LEFT JOIN kpi_scores ks ON rc.kpi_score_id = ks.id
        WHERE 1=1
    """
    params: list = []
    if team_filter:
        sql += " AND rc.team_id = ?"
        params.append(team_filter)
    if period_filter:
        sql += " AND rc.period = ?"
        params.append(period_filter)
    if status_filter:
        sql += " AND rc.status = ?"
        params.append(status_filter)
    sql += " ORDER BY rc.created_at DESC LIMIT 500"

    calculations = db.execute(sql, tuple(params))
    for row in calculations:
        if isinstance(row.get("variables_json"), str) and row["variables_json"]:
            try:
                row["variables_preview"] = row["variables_json"][:120]
            except Exception:
                row["variables_preview"] = ""
        elif isinstance(row.get("variables_json"), dict):
            row["variables_preview"] = json.dumps(row["variables_json"], ensure_ascii=False)[:120]
        else:
            row["variables_preview"] = ""

    team_map = _team_display_map(db)
    for row in calculations:
        row["team_display"] = team_map.get(row.get("team_id", ""), row.get("team_id", ""))

    rules_conditions = {"team_id": team_filter} if team_filter else None
    reward_rules = db.query("reward_rules", rules_conditions, order_by="team_id, kpi_grade", limit=300)
    for r in reward_rules:
        r["team_display"] = team_map.get(r.get("team_id", ""), r.get("team_id", ""))

    teams = db.query("teams", order_by="name", limit=500)
    ctx = _global_context(request)
    ctx["calculations"] = calculations
    ctx["reward_rules"] = reward_rules
    ctx["teams"] = teams
    ctx["team_filter"] = team_filter
    ctx["period_filter"] = period_filter
    ctx["status_filter"] = status_filter
    ctx["status_options"] = [
        RewardStatus.CALCULATED.value,
        RewardStatus.PENDING_APPROVAL.value,
        RewardStatus.APPROVED.value,
        RewardStatus.PAID.value,
    ]
    ctx["error"] = request.query_params.get("error", "")
    return render(request, "pages/salary.html", ctx)


@router.post("/calculate")
async def salary_calculate(
    team_id: str = Form(...),
    period: str = Form(...),
):
    db = Database.get_instance()
    team_id = team_id.strip()
    period = period.strip()
    if not team_id or not period:
        return RedirectResponse("/salary?error=missing", status_code=302)

    db.execute(
        "DELETE FROM reward_calculations WHERE team_id=? AND period=? AND status=?",
        (team_id, period, RewardStatus.CALCULATED.value),
    )

    sql_scores = """
        SELECT ks.*, kd.team_id AS def_team_id
        FROM kpi_scores ks
        JOIN kpi_definitions kd ON ks.kpi_def_id = kd.id
        WHERE kd.team_id = ? AND ks.period_key = ?
    """
    score_rows = db.execute(sql_scores, (team_id, period))

    employees = db.query("employees", {"team_id": team_id}, order_by="name", limit=2000)
    emp_ids = {e["id"] for e in employees}

    calc = CalcEngine(db)

    for row in score_rows:
        emp_id = row.get("employee_id") or ""
        if emp_id not in emp_ids:
            continue

        grade = (row.get("grade") or "").strip().upper()
        rules = db.query("reward_rules", {"team_id": team_id, "kpi_grade": grade}, limit=5)
        if not rules:
            rules = db.query("reward_rules", {"team_id": team_id, "kpi_grade": "*"}, limit=5)

        rule = rules[0] if rules else None
        formula = (rule.get("formula", "0") if rule else "0") or "0"
        total_score = float(row.get("total_score") or 0)

        variables = {
            "score": total_score,
            "grade_num": float(CalcEngine._grade_to_num(grade)),
            "base": 1000.0,
            "base_salary": 15000.0,
            "signed_amount": 80000.0,
        }

        try:
            amount = round(float(calc.evaluate_formula(formula, variables)), 2)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Salary formula failed team=%s emp=%s: %s", team_id, emp_id, exc)
            amount = 0.0

        db.insert(
            "reward_calculations",
            {
                "id": new_id(),
                "employee_id": emp_id,
                "team_id": team_id,
                "period": period,
                "kpi_score_id": row["id"],
                "rule_id": rule["id"] if rule else "",
                "calculated_amount": amount,
                "formula_used": formula,
                "variables_json": variables,
                "status": RewardStatus.CALCULATED.value,
                "created_at": datetime.utcnow().isoformat(),
            },
        )

    return RedirectResponse("/salary", status_code=302)
