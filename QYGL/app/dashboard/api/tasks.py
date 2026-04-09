"""P06: Task management — list, create, detail with feedback history."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.core.enums import TaskStatus
from app.core.uploads import save_upload
from app.dashboard.app import _global_context, get_user_team_filter, render

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

_TASK_STATUSES = {s.value for s in TaskStatus}
_SCORE_GRADES = frozenset({"A", "B", "C", "D"})


def _delete_task_and_related(db: Database, task_id: str) -> None:
    db.execute("DELETE FROM task_feedbacks WHERE task_id=?", (task_id,))
    db.execute("DELETE FROM escalations WHERE task_id=?", (task_id,))
    db.execute(
        "DELETE FROM task_dependencies WHERE upstream_task_id=? OR downstream_task_id=?",
        (task_id, task_id),
    )
    db.delete("tasks", task_id)


@router.get("", response_class=HTMLResponse)
async def task_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    status = request.query_params.get("status", "")
    team_id = request.query_params.get("team_id", "")
    employee_id = request.query_params.get("employee_id", "")

    tasks: list = []
    completed_count = 0

    if user_teams is not None and not user_teams:
        pass
    elif user_teams is not None and team_id and team_id not in user_teams:
        pass
    else:
        conditions: dict = {}
        if status:
            conditions["status"] = status
        if employee_id:
            conditions["employee_id"] = employee_id
        if user_teams is not None:
            conditions["team_id"] = team_id if team_id else user_teams
        elif team_id:
            conditions["team_id"] = team_id
        tasks = db.query("tasks", conditions or None, order_by="created_at DESC", limit=200)

        completed_conds: dict = {"status": "completed"}
        if user_teams is not None:
            completed_conds["team_id"] = team_id if team_id else user_teams
        elif team_id:
            completed_conds["team_id"] = team_id
        completed_count = db.count("tasks", completed_conds)

    ctx["tasks"] = tasks
    ctx["status_filter"] = status
    ctx["team_filter"] = team_id
    ctx["employee_filter"] = employee_id
    ctx["statuses"] = [s.value for s in TaskStatus]
    ctx["teams"] = db.query("teams", order_by="name", limit=100)
    if user_teams is not None:
        ctx["teams"] = [t for t in ctx["teams"] if t["id"] in user_teams]
    ctx["stats"] = {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t.get("status") == "pending"),
        "in_progress": sum(1 for t in tasks if t.get("status") == "in_progress"),
        "overdue": sum(1 for t in tasks if t.get("status") == "overdue"),
        "completed": completed_count,
    }

    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in ctx["teams"]}
    emp_ids = {t.get("employee_id") for t in tasks if t.get("employee_id")}
    employee_map: dict[str, str] = {}
    for eid in emp_ids:
        emp = db.get_by_id("employees", eid)
        if emp:
            employee_map[eid] = emp.get("name") or eid
    ctx["team_map"] = team_map
    ctx["employee_map"] = employee_map

    return render(request, "pages/tasks.html", ctx)


@router.post("")
async def create_task(
    request: Request,
    title: str = Form(...),
    team_id: str = Form(""),
    employee_id: str = Form(""),
    description: str = Form(""),
    deadline: str = Form(""),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    tid = (team_id or "").strip()
    if not tid and user_teams and len(user_teams) == 1:
        tid = user_teams[0]
    if user_teams is not None and tid and tid not in user_teams:
        raise HTTPException(status_code=403, detail="无权为该团队创建任务")
    if not tid:
        raise HTTPException(status_code=400, detail="请选择团队")
    task_data = {
        "id": new_id(),
        "title": title,
        "team_id": tid,
        "employee_id": employee_id,
        "description": description,
        "status": TaskStatus.PENDING.value,
        "created_at": datetime.now().isoformat(),
    }
    if deadline:
        task_data["deadline_at"] = deadline

    db.insert("tasks", task_data)

    try:
        from app.safety.approval import ApprovalGateway
        from app.core.enums import ApprovalType, Confidence

        gateway = ApprovalGateway.get_instance()
        await gateway.submit(
            action_type=ApprovalType.TASK_DISPATCH,
            team_id=tid,
            title=f"派发任务: {title}",
            detail={"task_id": task_data["id"], "employee_id": employee_id, "title": title},
            confidence=Confidence.B,
            source_agent="dashboard",
            reasoning="用户通过后台创建任务",
        )
    except Exception as e:
        logger.warning("Approval gateway submission failed for task %s: %s", task_data["id"], e)

    return RedirectResponse("/tasks?msg=" + quote("任务创建成功"), status_code=302)


@router.get("/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: str):
    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")

    ctx = _global_context(request)
    ctx["task"] = task
    ctx["feedback_list"] = db.query("task_feedbacks", {"task_id": task_id}, order_by="submitted_at DESC")
    ctx["employee"] = db.get_by_id("employees", task.get("employee_id", "")) if task.get("employee_id") else None
    ctx["team"] = db.get_by_id("teams", task.get("team_id", "")) if task.get("team_id") else None
    ctx["statuses"] = [s.value for s in TaskStatus]
    ctx["feedback_error"] = request.query_params.get("feedback_error", "")

    if request.headers.get("HX-Request"):
        return render(request, "partials/task_detail.html", ctx)
    return render(request, "pages/task_detail.html", ctx)


@router.post("/{task_id}/status")
async def update_task_status(request: Request, task_id: str, status: str = Form(...)):
    if status not in _TASK_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid task status")

    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")

    data: dict = {"status": status}
    if status == TaskStatus.COMPLETED.value:
        data["completed_at"] = datetime.now().isoformat()

    db.update("tasks", task_id, data)
    return RedirectResponse(f"/tasks/{task_id}?msg=" + quote("状态已更新"), status_code=302)


@router.post("/{task_id}/feedback")
async def add_task_feedback(request: Request, task_id: str, content: str = Form(...)):
    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")

    fb = {
        "id": new_id(),
        "task_id": task_id,
        "employee_id": task.get("employee_id") or "",
        "content": content,
        "feedback_type": "text",
        "file_path": "",
        "submitted_at": datetime.now().isoformat(),
    }
    db.insert("task_feedbacks", fb)
    return RedirectResponse(f"/tasks/{task_id}", status_code=302)


@router.post("/{task_id}/feedback-file")
async def add_task_feedback_file(
    task_id: str,
    request: Request,
    file: UploadFile = File(...),
    content: str = Form(""),
):
    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")

    if not file.filename:
        return RedirectResponse(
            f"/tasks/{task_id}?feedback_error={quote('请选择要上传的文件')}",
            status_code=302,
        )

    try:
        meta = await save_upload(file)
    except ValueError as e:
        return RedirectResponse(
            f"/tasks/{task_id}?feedback_error={quote(str(e))}",
            status_code=302,
        )

    text = content.strip() if content else ""
    if not text:
        text = file.filename or "附件"

    fb = {
        "id": new_id(),
        "task_id": task_id,
        "employee_id": task.get("employee_id") or "",
        "content": text,
        "feedback_type": "file",
        "file_path": meta["path"],
        "submitted_at": datetime.now().isoformat(),
    }
    db.insert("task_feedbacks", fb)
    return RedirectResponse(f"/tasks/{task_id}", status_code=302)


@router.post("/{task_id}/delete")
async def delete_task(request: Request, task_id: str):
    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")
    _delete_task_and_related(db, task_id)
    return RedirectResponse("/tasks", status_code=302)


@router.post("/{task_id}/score")
async def score_task(
    request: Request,
    task_id: str,
    score_quality: float = Form(...),
    score_timeliness: float = Form(...),
    score_complexity: float = Form(...),
    grade: str = Form(...),
    feedback: str = Form(""),
):
    db = Database.get_instance()
    task = db.get_by_id("tasks", task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and task.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") != TaskStatus.SUBMITTED.value:
        raise HTTPException(status_code=400, detail="Only submitted tasks can be scored")

    grade_upper = grade.strip().upper()
    if grade_upper not in _SCORE_GRADES:
        raise HTTPException(status_code=400, detail="grade must be A, B, C, or D")

    for name, val in (
        ("score_quality", score_quality),
        ("score_timeliness", score_timeliness),
        ("score_complexity", score_complexity),
    ):
        if not 0 <= val <= 100:
            raise HTTPException(status_code=400, detail=f"{name} must be between 0 and 100")

    score_avg = round((score_quality + score_timeliness + score_complexity) / 3.0, 2)

    db.update(
        "tasks",
        task_id,
        {
            "score": score_avg,
            "score_quality": score_quality,
            "score_timeliness": score_timeliness,
            "score_complexity": score_complexity,
            "grade": grade_upper,
            "feedback": feedback,
            "status": TaskStatus.SCORED.value,
        },
    )
    return RedirectResponse(f"/tasks/{task_id}?msg=" + quote("评分已提交"), status_code=302)
