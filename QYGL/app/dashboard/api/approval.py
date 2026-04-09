"""P05: Approval center — dual-column layout, confidence filtering, approve/reject."""

from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse

from app.core.database import Database
from app.core.enums import ApprovalStatus, ApprovalType, Confidence
from app.dashboard.app import _global_context, get_user_team_filter, render

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _approval_stats(db: Database, user_teams: list[str] | None) -> tuple[int, int]:
    if user_teams is not None and not user_teams:
        return 0, 0
    approved_c: dict = {"status": "approved"}
    rejected_c: dict = {"status": "rejected"}
    if user_teams is not None:
        approved_c["team_id"] = user_teams
        rejected_c["team_id"] = user_teams
    return db.count("approval_requests", approved_c), db.count("approval_requests", rejected_c)


def _parse_detail_and_linked(db: Database, approval: dict) -> tuple[dict, list[dict]]:
    raw = approval.get("detail_json", "{}")
    if isinstance(raw, str):
        try:
            detail = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            detail = {}
    elif isinstance(raw, dict):
        detail = raw
    else:
        detail = {}

    linked: list[dict] = []
    team_id = approval.get("team_id") or ""
    if team_id:
        team = db.get_by_id("teams", team_id)
        if team:
            name = team.get("display_name") or team.get("name") or team_id
            linked.append({"label": "所属团队", "name": name, "url": f"/teams/{team['id']}"})

    emp_name = (detail.get("employee") or "").strip()
    if emp_name:
        emp_rows = db.execute(
            "SELECT id, name FROM employees WHERE name=? LIMIT 1",
            (emp_name,),
        )
        if emp_rows:
            linked.append(
                {
                    "label": "相关员工",
                    "name": emp_rows[0]["name"],
                    "url": f"/employees/{emp_rows[0]['id']}",
                }
            )

    return detail, linked


@router.get("", response_class=HTMLResponse)
async def approval_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    status = request.query_params.get("status", "")
    confidence = request.query_params.get("confidence", "")
    approval_type = request.query_params.get("type", "")
    urgency = request.query_params.get("urgency", "")

    approvals: list = []
    if user_teams is not None and not user_teams:
        pass
    else:
        conditions: dict = {}
        if status:
            conditions["status"] = status
        if confidence:
            conditions["confidence"] = confidence
        if user_teams is not None:
            conditions["team_id"] = user_teams

        approvals = db.query("approval_requests", conditions or None, order_by="priority ASC, created_at DESC", limit=200)

        if approval_type:
            approvals = [a for a in approvals if a.get("type") == approval_type]
        if urgency:
            approvals = [a for a in approvals if a.get("priority", 2) <= int(urgency)]

    approved_n, rejected_n = _approval_stats(db, user_teams)

    ctx["approvals"] = approvals
    ctx["status_filter"] = status
    ctx["confidence_filter"] = confidence
    ctx["type_filter"] = approval_type
    ctx["urgency_filter"] = urgency
    ctx["statuses"] = [s.value for s in ApprovalStatus]
    ctx["types"] = [t.value for t in ApprovalType]
    ctx["confidences"] = [c.value for c in Confidence]
    ctx["stats"] = {
        "total": len(approvals),
        "pending": sum(1 for a in approvals if a.get("status") == "pending"),
        "approved": approved_n,
        "rejected": rejected_n,
    }
    ctx["flash_msg"] = request.query_params.get("msg", "")

    return render(request, "pages/approval.html", ctx)


@router.post("/batch-approve")
async def batch_approve(request: Request, ids: str = Form(...)):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    now = datetime.utcnow().isoformat()
    for aid in id_list:
        approval = db.get_by_id("approval_requests", aid)
        if not approval or approval.get("status") != "pending":
            continue
        if user_teams is not None and approval.get("team_id") not in user_teams:
            continue
        db.update(
            "approval_requests",
            aid,
            {
                "status": ApprovalStatus.APPROVED.value,
                "resolved_at": now,
            },
        )
    q = urlencode({"msg": "批量批准成功"})
    return RedirectResponse(f"/approvals?{q}", status_code=302)


@router.post("/batch-reject")
async def batch_reject(request: Request, ids: str = Form(...), reason: str = Form("批量驳回")):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    r = (reason or "").strip() or "批量驳回"
    now = datetime.utcnow().isoformat()
    for aid in id_list:
        approval = db.get_by_id("approval_requests", aid)
        if not approval or approval.get("status") != "pending":
            continue
        if user_teams is not None and approval.get("team_id") not in user_teams:
            continue
        db.update(
            "approval_requests",
            aid,
            {
                "status": ApprovalStatus.REJECTED.value,
                "rejection_reason": r,
                "resolved_at": now,
            },
        )
    q = urlencode({"msg": "批量驳回已处理"})
    return RedirectResponse(f"/approvals?{q}", status_code=302)


@router.get("/{approval_id}", response_class=HTMLResponse)
async def approval_detail(request: Request, approval_id: str):
    db = Database.get_instance()
    approval = db.get_by_id("approval_requests", approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and approval.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Approval not found")

    ctx = _global_context(request)
    ctx["approval"] = approval
    detail, linked = _parse_detail_and_linked(db, approval)
    ctx["detail"] = detail
    ctx["linked"] = linked

    if request.headers.get("HX-Request"):
        return render(request, "partials/approval_detail.html", ctx)

    list_conds = {"team_id": user_teams} if user_teams is not None else None
    ctx["approvals"] = db.query("approval_requests", list_conds, order_by="priority ASC, created_at DESC", limit=200)
    ctx["statuses"] = [s.value for s in ApprovalStatus]
    ctx["types"] = [t.value for t in ApprovalType]
    ctx["confidences"] = [c.value for c in Confidence]
    ctx["status_filter"] = ""
    ctx["confidence_filter"] = ""
    ctx["type_filter"] = ""
    ctx["urgency_filter"] = ""
    all_approvals = ctx["approvals"]
    approved_n, rejected_n = _approval_stats(db, user_teams)
    ctx["stats"] = {
        "total": len(all_approvals),
        "pending": sum(1 for a in all_approvals if a.get("status") == "pending"),
        "approved": approved_n,
        "rejected": rejected_n,
    }
    ctx["flash_msg"] = request.query_params.get("msg", "")
    return render(request, "pages/approval.html", ctx)


@router.post("/{approval_id}/approve")
async def approve(request: Request, approval_id: str):
    db = Database.get_instance()
    approval = db.get_by_id("approval_requests", approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and approval.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Approval not found")

    db.update(
        "approval_requests",
        approval_id,
        {
            "status": ApprovalStatus.APPROVED.value,
            "resolved_at": datetime.utcnow().isoformat(),
        },
    )

    return RedirectResponse("/approvals?" + urlencode({"msg": "已批准"}), status_code=302)


@router.post("/{approval_id}/reject")
async def reject(request: Request, approval_id: str, reason: str = Form(...)):
    db = Database.get_instance()
    approval = db.get_by_id("approval_requests", approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    user_teams = get_user_team_filter(request)
    if user_teams is not None and approval.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Approval not found")

    if not reason.strip():
        raise HTTPException(status_code=400, detail="拒绝原因不能为空")

    db.update(
        "approval_requests",
        approval_id,
        {
            "status": ApprovalStatus.REJECTED.value,
            "rejection_reason": reason,
            "resolved_at": datetime.utcnow().isoformat(),
        },
    )

    return RedirectResponse("/approvals?" + urlencode({"msg": "已驳回"}), status_code=302)
