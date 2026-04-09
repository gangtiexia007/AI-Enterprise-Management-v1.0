"""Employee self-service portal — /my routes (T3 primary; others with linked employee_id)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.core.enums import DisputeType, TaskStatus
from app.dashboard.app import _global_context, render

router = APIRouter(tags=["my"])

_DISPUTE_TYPES = {t.value for t in DisputeType}
_SUBMITTABLE = {TaskStatus.DISPATCHED.value, TaskStatus.IN_PROGRESS.value}


def _resolve_employee(request: Request) -> tuple[str | None, dict | None]:
    user = getattr(request.state, "user", None) or {}
    eid = (user.get("employee_id") or "").strip()
    if not eid:
        return None, None
    emp = Database.get_instance().get_by_id("employees", eid)
    return eid, emp


@router.get("", response_class=HTMLResponse)
async def my_dashboard(request: Request):
    ctx = _global_context(request)
    eid, emp = _resolve_employee(request)
    ctx["employee"] = emp
    ctx["employee_id_linked"] = bool(eid and emp)
    ctx["dispute_types"] = [t.value for t in DisputeType]

    if not eid or not emp:
        return render(request, "pages/my_dashboard.html", ctx)

    db = Database.get_instance()
    tasks = db.query("tasks", {"employee_id": eid}, order_by="deadline_at ASC, created_at DESC", limit=50)
    ctx["my_tasks_preview"] = tasks[:8]

    scores = db.query("kpi_scores", {"employee_id": eid}, order_by="scored_at DESC", limit=20)
    kpi_map = {k["id"]: k for k in db.query("kpi_definitions", limit=500)}
    for s in scores:
        kd = kpi_map.get(s.get("kpi_def_id", ""))
        s["kpi_name"] = (kd or {}).get("name", s.get("kpi_def_id", ""))[:32]
        s["kpi_period"] = (kd or {}).get("period", "")
    ctx["my_kpi_preview"] = scores[:6]

    team = db.get_by_id("teams", emp.get("team_id") or "") if emp.get("team_id") else None
    ctx["my_team"] = team

    return render(request, "pages/my_dashboard.html", ctx)


@router.get("/tasks", response_class=HTMLResponse)
async def my_tasks(request: Request):
    ctx = _global_context(request)
    eid, emp = _resolve_employee(request)
    ctx["employee"] = emp
    if not eid or not emp:
        ctx["tasks"] = []
        ctx["no_employee"] = True
        return render(request, "pages/my_tasks.html", ctx)

    db = Database.get_instance()
    ctx["tasks"] = db.query("tasks", {"employee_id": eid}, order_by="deadline_at ASC, created_at DESC", limit=200)
    ctx["no_employee"] = False
    return render(request, "pages/my_tasks.html", ctx)


@router.get("/kpi", response_class=HTMLResponse)
async def my_kpi(request: Request):
    ctx = _global_context(request)
    eid, emp = _resolve_employee(request)
    ctx["employee"] = emp
    if not eid or not emp:
        ctx["scores"] = []
        ctx["no_employee"] = True
        return render(request, "pages/my_kpi.html", ctx)

    db = Database.get_instance()
    scores = db.query("kpi_scores", {"employee_id": eid}, order_by="period_key DESC, scored_at DESC", limit=200)
    kpi_map = {k["id"]: k for k in db.query("kpi_definitions", limit=500)}
    for s in scores:
        kd = kpi_map.get(s.get("kpi_def_id", ""))
        s["kpi_name"] = (kd or {}).get("name", "—")
        s["kpi_period_def"] = (kd or {}).get("period", "")
    ctx["scores"] = scores
    ctx["no_employee"] = False
    return render(request, "pages/my_kpi.html", ctx)


@router.post("/tasks/{task_id}/submit")
async def submit_my_task(request: Request, task_id: str):
    eid, emp = _resolve_employee(request)
    if not eid or not emp:
        return RedirectResponse("/my/tasks", status_code=302)

    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task or (task.get("employee_id") or "").strip() != eid:
        raise HTTPException(status_code=404, detail="Task not found")

    st = task.get("status") or ""
    if st not in _SUBMITTABLE:
        return RedirectResponse("/my/tasks", status_code=302)

    db.update("tasks", task_id, {"status": TaskStatus.SUBMITTED.value})
    return RedirectResponse("/my/tasks", status_code=302)


@router.post("/dispute")
async def file_my_dispute(
    request: Request,
    type: str = Form(...),
    target_type: str = Form(""),
    target_id: str = Form(""),
    employee_reason: str = Form(...),
):
    eid, emp = _resolve_employee(request)
    if not eid or not emp:
        return RedirectResponse("/my", status_code=302)

    dtype = (type or "").strip()
    if dtype not in _DISPUTE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid dispute type")

    db = Database.get_instance()
    team_id = (emp.get("team_id") or "").strip()
    db.insert("disputes", {
        "id": new_id(),
        "type": dtype,
        "team_id": team_id,
        "employee_id": eid,
        "target_type": (target_type or "").strip(),
        "target_id": (target_id or "").strip(),
        "employee_reason": (employee_reason or "").strip(),
    })
    return RedirectResponse("/my", status_code=302)
