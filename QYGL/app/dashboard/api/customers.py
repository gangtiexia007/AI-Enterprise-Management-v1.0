"""F42: Customer management — list, create, detail, contacts, feedbacks."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.dashboard.app import _global_context, get_user_team_filter, render

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])

_CUSTOMER_STATUSES = frozenset({"active", "inactive", "churned"})


@router.get("", response_class=HTMLResponse)
async def customers_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    status = request.query_params.get("status", "")
    team_id = request.query_params.get("team_id", "")

    customers: list = []

    if user_teams is not None and not user_teams:
        pass
    elif user_teams is not None and team_id and team_id not in user_teams:
        pass
    else:
        conditions: dict = {}
        if status:
            conditions["status"] = status
        if user_teams is not None:
            conditions["team_id"] = team_id if team_id else user_teams
        elif team_id:
            conditions["team_id"] = team_id
        customers = db.query("customers", conditions or None, order_by="created_at DESC", limit=200)

    ctx["customers"] = customers
    ctx["status_filter"] = status
    ctx["team_filter"] = team_id
    ctx["teams"] = db.query("teams", order_by="name", limit=100)
    if user_teams is not None:
        ctx["teams"] = [t for t in ctx["teams"] if t["id"] in user_teams]

    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in ctx["teams"]}
    emp_ids = {c.get("assigned_employee_id") for c in customers if c.get("assigned_employee_id")}
    employee_map: dict[str, str] = {}
    for eid in emp_ids:
        emp = db.get_by_id("employees", eid)
        if emp:
            employee_map[eid] = emp.get("name") or eid
    ctx["team_map"] = team_map
    ctx["employee_map"] = employee_map

    ctx["stats"] = {
        "total": len(customers),
        "active": sum(1 for c in customers if c.get("status") == "active"),
        "inactive": sum(1 for c in customers if c.get("status") == "inactive"),
        "churned": sum(1 for c in customers if c.get("status") == "churned"),
    }

    return render(request, "pages/customers.html", ctx)


@router.get("/{customer_id}", response_class=HTMLResponse)
async def customer_detail(request: Request, customer_id: str):
    db = Database.get_instance()
    customer = db.get_by_id("customers", customer_id)
    if not customer:
        return RedirectResponse("/customers?msg=" + quote("客户不存在"), status_code=302)

    user_teams = get_user_team_filter(request)
    if user_teams is not None and customer.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Customer not found")

    ctx = _global_context(request)
    ctx["customer"] = customer
    ctx["contacts"] = db.query(
        "customer_contacts", {"customer_id": customer_id}, order_by="created_at DESC"
    )
    ctx["feedbacks"] = db.query(
        "customer_feedbacks", {"customer_id": customer_id}, order_by="created_at DESC"
    )
    ctx["team"] = db.get_by_id("teams", customer.get("team_id", "")) if customer.get("team_id") else None
    ctx["employee"] = (
        db.get_by_id("employees", customer.get("assigned_employee_id", ""))
        if customer.get("assigned_employee_id")
        else None
    )

    employees = db.query("employees", {"team_id": customer["team_id"]} if customer.get("team_id") else None, limit=200)
    ctx["employees"] = employees

    emp_ids = {c.get("employee_id") for c in ctx["contacts"] if c.get("employee_id")}
    employee_map: dict[str, str] = {}
    for eid in emp_ids:
        emp = db.get_by_id("employees", eid)
        if emp:
            employee_map[eid] = emp.get("name") or eid
    ctx["employee_map"] = employee_map

    return render(request, "pages/customer_detail.html", ctx)


@router.post("")
async def create_customer(
    request: Request,
    name: str = Form(...),
    company: str = Form(""),
    team_id: str = Form(""),
    assigned_employee_id: str = Form(""),
    contact_info: str = Form(""),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    tid = (team_id or "").strip()
    if not tid and user_teams and len(user_teams) == 1:
        tid = user_teams[0]
    if user_teams is not None and tid and tid not in user_teams:
        raise HTTPException(status_code=403, detail="无权为该团队创建客户")
    if not tid:
        raise HTTPException(status_code=400, detail="请选择团队")

    db.insert("customers", {
        "id": new_id(),
        "name": name,
        "company": company,
        "team_id": tid,
        "assigned_employee_id": assigned_employee_id,
        "contact_info": contact_info,
        "status": "active",
        "created_at": datetime.now().isoformat(),
    })
    return RedirectResponse("/customers?msg=" + quote("客户已创建"), status_code=302)


@router.post("/{customer_id}/status")
async def update_customer_status(request: Request, customer_id: str, status: str = Form(...)):
    if status not in _CUSTOMER_STATUSES:
        raise HTTPException(status_code=400, detail="无效的客户状态")

    db = Database.get_instance()
    customer = db.get_by_id("customers", customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and customer.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.update("customers", customer_id, {"status": status})
    return RedirectResponse(f"/customers/{customer_id}?msg=" + quote("状态已更新"), status_code=302)


@router.post("/{customer_id}/contact")
async def add_contact_record(
    request: Request,
    customer_id: str,
    content: str = Form(...),
    contact_type: str = Form("note"),
    employee_id: str = Form(""),
):
    db = Database.get_instance()
    customer = db.get_by_id("customers", customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and customer.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.insert("customer_contacts", {
        "id": new_id(),
        "customer_id": customer_id,
        "employee_id": employee_id,
        "content": content,
        "contact_type": contact_type,
        "created_at": datetime.now().isoformat(),
    })
    return RedirectResponse(f"/customers/{customer_id}?msg=" + quote("联系记录已添加"), status_code=302)


@router.post("/{customer_id}/feedback")
async def add_feedback(
    request: Request,
    customer_id: str,
    content: str = Form(...),
    feedback_type: str = Form("general"),
):
    db = Database.get_instance()
    customer = db.get_by_id("customers", customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and customer.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.insert("customer_feedbacks", {
        "id": new_id(),
        "customer_id": customer_id,
        "feedback_type": feedback_type,
        "content": content,
        "status": "open",
        "created_at": datetime.now().isoformat(),
    })
    return RedirectResponse(f"/customers/{customer_id}?msg=" + quote("反馈已记录"), status_code=302)


@router.post("/{customer_id}/delete")
async def delete_customer(request: Request, customer_id: str):
    db = Database.get_instance()
    customer = db.get_by_id("customers", customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and customer.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.execute("DELETE FROM customer_contacts WHERE customer_id=?", (customer_id,))
    db.execute("DELETE FROM customer_feedbacks WHERE customer_id=?", (customer_id,))
    db.delete("customers", customer_id)
    return RedirectResponse("/customers?msg=" + quote("客户已删除"), status_code=302)
