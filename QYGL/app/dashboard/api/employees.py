"""Employee management — list, detail, CRUD from dashboard."""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse

from app.core.database import Database, new_id
from app.core.employee_manager import EmployeeManager
from app.core.exceptions import EmployeeNotFound, ValidationError
from app.dashboard.app import _global_context, get_user_team_filter, render

logger = logging.getLogger(__name__)

router = APIRouter(tags=["employees"])

ROLE_VALUES = ("boss", "manager", "employee")


def _enrich_employees(db: Database, rows: list[dict]) -> None:
    teams = db.query("teams", order_by="name", limit=500)
    team_map = {t["id"]: t for t in teams}
    emp_name = {e["id"]: e["name"] for e in db.query("employees", limit=2000)}
    for e in rows:
        tid = e.get("team_id") or ""
        t = team_map.get(tid)
        if t:
            e["team_name"] = t.get("display_name") or t.get("name") or tid[:8]
        else:
            e["team_name"] = "—" if not tid else tid[:8]
        mid = e.get("direct_manager_id") or ""
        e["manager_name"] = emp_name.get(mid, "") if mid else ""


def _list_context(
    request: Request,
    team_filter: str,
    role_filter: str,
    highlight_id: str = "",
    error: str = "",
) -> dict:
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)

    employees: list = []
    if user_teams is not None and not user_teams:
        pass
    elif user_teams is not None and team_filter and team_filter not in user_teams:
        pass
    else:
        conditions: dict = {}
        if user_teams is not None:
            conditions["team_id"] = team_filter if team_filter else user_teams
        elif team_filter:
            conditions["team_id"] = team_filter
        if role_filter:
            conditions["role"] = role_filter
        employees = db.query("employees", conditions or None, order_by="name", limit=2000)
    _enrich_employees(db, employees)

    coaching_rows = db.query("coaching_records", order_by="created_at DESC", limit=2000)
    coach_ids = {c.get("coach_id") for c in coaching_rows if c.get("coach_id")}
    coach_names: dict[str, str] = {}
    for cid in coach_ids:
        er = db.get_by_id("employees", cid)
        if er:
            coach_names[cid] = er.get("name") or cid
        else:
            ur = db.get_by_id("dashboard_users", cid)
            coach_names[cid] = (
                (ur or {}).get("display_name")
                or (ur or {}).get("username")
                or (cid[:8] if cid else "")
            )
    for c in coaching_rows:
        cid = c.get("coach_id") or ""
        c["coach_display"] = coach_names.get(cid, cid[:8] if cid else "—")

    if user_teams is not None:
        coaching_rows = [
            c for c in coaching_rows if (c.get("team_id") or "") in user_teams
        ]

    by_emp: dict[str, list] = defaultdict(list)
    for c in coaching_rows:
        by_emp[c.get("employee_id", "")].append(c)
    for e in employees:
        e["coaching_records"] = by_emp.get(e["id"], [])

    teams = db.query("teams", order_by="name", limit=500)
    if user_teams is not None:
        teams = [t for t in teams if t["id"] in user_teams]
    ctx = _global_context(request)
    ctx["employees"] = employees
    ctx["teams"] = teams
    ctx["team_filter"] = team_filter
    ctx["role_filter"] = role_filter
    ctx["roles"] = ROLE_VALUES
    ctx["highlight_id"] = highlight_id
    ctx["error"] = error
    return ctx


@router.get("", response_class=HTMLResponse)
async def employee_list_page(request: Request):
    team_filter = request.query_params.get("team_id", "")
    role_filter = request.query_params.get("role", "")
    err = request.query_params.get("error", "")
    ctx = _list_context(request, team_filter, role_filter, error=err)
    return render(request, "pages/employees.html", ctx)


@router.get("/{employee_id}", response_class=HTMLResponse)
async def employee_detail_page(request: Request, employee_id: str):
    db = Database.get_instance()
    emp = db.get_by_id("employees", employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and (emp.get("team_id") or "") not in user_teams:
        raise HTTPException(status_code=404, detail="Employee not found")
    team_filter = request.query_params.get("team_id", "")
    role_filter = request.query_params.get("role", "")
    ctx = _list_context(request, team_filter, role_filter, highlight_id=employee_id)
    return render(request, "pages/employees.html", ctx)


@router.post("")
async def create_employee(
    request: Request,
    name: str = Form(...),
    team_id: str = Form(""),
    role: str = Form("employee"),
    department: str = Form(""),
    direct_manager_id: str = Form(""),
    join_date: str = Form(""),
    birthday: str = Form(""),
    notes: str = Form(""),
):
    if role not in ROLE_VALUES:
        role = "employee"
    user_teams = get_user_team_filter(request)
    tid = (team_id or "").strip()
    if not tid and user_teams and len(user_teams) == 1:
        tid = user_teams[0]
    if user_teams is not None and tid and tid not in user_teams:
        ctx = _list_context(request, "", "", error="无权在该团队下创建员工")
        return render(request, "pages/employees.html", ctx, status_code=403)
    if user_teams is not None and not tid:
        ctx = _list_context(request, "", "", error="请选择团队")
        return render(request, "pages/employees.html", ctx, status_code=400)
    mgr = EmployeeManager()
    try:
        mgr.create_employee({
            "name": name.strip(),
            "team_id": tid,
            "role": role,
            "department": department.strip(),
            "direct_manager_id": direct_manager_id.strip(),
            "join_date": join_date.strip() or None,
            "birthday": birthday.strip() or None,
            "notes": notes.strip(),
        })
    except ValidationError as e:
        ctx = _list_context(request, "", "", error=str(e))
        return render(request, "pages/employees.html", ctx, status_code=400)
    return RedirectResponse("/employees?" + urlencode({"msg": "员工已添加"}), status_code=302)


@router.post("/{employee_id}/update")
async def update_employee(
    request: Request,
    employee_id: str,
    name: str = Form(...),
    team_id: str = Form(""),
    role: str = Form("employee"),
    department: str = Form(""),
    direct_manager_id: str = Form(""),
    join_date: str = Form(""),
    birthday: str = Form(""),
    notes: str = Form(""),
):
    if role not in ROLE_VALUES:
        role = "employee"
    db = Database.get_instance()
    existing = db.get_by_id("employees", employee_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and (existing.get("team_id") or "") not in user_teams:
        raise HTTPException(status_code=404, detail="Employee not found")
    new_tid = (team_id or "").strip()
    if user_teams is not None and not new_tid:
        ctx = _list_context(request, "", "", highlight_id=employee_id, error="请选择团队")
        return render(request, "pages/employees.html", ctx, status_code=400)
    if user_teams is not None and new_tid not in user_teams:
        ctx = _list_context(request, "", "", highlight_id=employee_id, error="无权将员工调整到该团队")
        return render(request, "pages/employees.html", ctx, status_code=403)
    mgr = EmployeeManager()
    try:
        mgr.update_employee(employee_id, {
            "name": name.strip(),
            "team_id": new_tid,
            "role": role,
            "department": department.strip(),
            "direct_manager_id": direct_manager_id.strip(),
            "join_date": join_date.strip() or None,
            "birthday": birthday.strip() or None,
            "notes": notes.strip(),
        })
    except EmployeeNotFound:
        raise HTTPException(status_code=404, detail="Employee not found")
    except ValidationError as e:
        ctx = _list_context(request, "", "", highlight_id=employee_id, error=str(e))
        return render(request, "pages/employees.html", ctx, status_code=400)
    return RedirectResponse("/employees", status_code=302)


@router.post("/{employee_id}/coaching")
async def add_coaching_record(
    request: Request,
    employee_id: str,
    content: str = Form(...),
    tags: str = Form(""),
):
    db = Database.get_instance()
    emp = db.get_by_id("employees", employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and (emp.get("team_id") or "") not in user_teams:
        raise HTTPException(status_code=404, detail="Employee not found")

    user = getattr(request.state, "user", None) or {}
    coach_id = (user.get("employee_id") or "").strip() or (user.get("id") or "").strip()
    if not coach_id:
        raise HTTPException(status_code=400, detail="无法确定辅导人身份")

    emp = db.get_by_id("employees", employee_id)
    team_id = (emp or {}).get("team_id") or ""

    db.insert("coaching_records", {
        "id": new_id(),
        "employee_id": employee_id,
        "coach_id": coach_id,
        "team_id": team_id,
        "content": content.strip(),
        "tags": tags.strip(),
    })
    return RedirectResponse(f"/employees/{employee_id}", status_code=302)


@router.post("/{employee_id}/delete")
async def delete_employee(request: Request, employee_id: str):
    db = Database.get_instance()
    emp = db.get_by_id("employees", employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and (emp.get("team_id") or "") not in user_teams:
        raise HTTPException(status_code=404, detail="Employee not found")
    try:
        db.delete("employees", employee_id)
    except sqlite3.IntegrityError:
        logger.warning("delete employee %s blocked by FK", employee_id)

        return RedirectResponse(
            "/employees?error=" + quote("无法删除：该员工仍被任务或其他数据引用", safe=""),
            status_code=302,
        )
    return RedirectResponse("/employees", status_code=302)
