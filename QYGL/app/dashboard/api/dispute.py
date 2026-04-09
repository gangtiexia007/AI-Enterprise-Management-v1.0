"""P09: Dispute center — dual-column, evidence chain, resolve/overturn."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database
from app.core.enums import DisputeStatus, DisputeType
from app.dashboard.app import templates, _global_context, render

router = APIRouter(prefix="/disputes", tags=["disputes"])


@router.get("", response_class=HTMLResponse)
async def dispute_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    status = request.query_params.get("status", "")
    dtype = request.query_params.get("type", "")

    conditions: dict = {}
    if status:
        conditions["status"] = status

    disputes = db.query("disputes", conditions or None, order_by="created_at DESC", limit=200)

    if dtype:
        disputes = [d for d in disputes if d.get("type") == dtype]

    for d in disputes:
        emp = db.get_by_id("employees", d.get("employee_id", ""))
        d["employee_name"] = emp.get("name", "未知") if emp else "未知"

    ctx["disputes"] = disputes
    ctx["status_filter"] = status
    ctx["type_filter"] = dtype
    ctx["statuses"] = [s.value for s in DisputeStatus]
    ctx["types"] = [t.value for t in DisputeType]
    ctx["stats"] = {
        "total": len(disputes),
        "filed": sum(1 for d in disputes if d.get("status") == "filed"),
        "resolved": sum(1 for d in disputes if d.get("status") == "resolved"),
        "overturned": sum(1 for d in disputes if d.get("status") == "overturned"),
    }

    return render(request, "pages/dispute.html", ctx)


@router.get("/{dispute_id}", response_class=HTMLResponse)
async def dispute_detail(request: Request, dispute_id: str):
    db = Database.get_instance()
    dispute = db.get_by_id("disputes", dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    ctx = _global_context(request)
    ctx["dispute"] = dispute
    ctx["employee"] = db.get_by_id("employees", dispute.get("employee_id", ""))

    import json
    evidence_raw = dispute.get("evidence_json", "[]")
    if isinstance(evidence_raw, str):
        try:
            ctx["evidence"] = json.loads(evidence_raw)
        except json.JSONDecodeError:
            ctx["evidence"] = []
    else:
        ctx["evidence"] = evidence_raw

    if request.headers.get("HX-Request"):
        return render(request, "partials/dispute_detail.html", ctx)

    all_disputes = db.query("disputes", order_by="created_at DESC", limit=200)
    for d in all_disputes:
        emp = db.get_by_id("employees", d.get("employee_id", ""))
        d["employee_name"] = emp.get("name", "未知") if emp else "未知"
    ctx["disputes"] = all_disputes
    ctx["statuses"] = [s.value for s in DisputeStatus]
    ctx["types"] = [t.value for t in DisputeType]
    ctx["status_filter"] = ""
    ctx["type_filter"] = ""
    ctx["stats"] = {
        "total": len(all_disputes),
        "filed": sum(1 for d in all_disputes if d.get("status") == "filed"),
        "resolved": sum(1 for d in all_disputes if d.get("status") == "resolved"),
        "overturned": sum(1 for d in all_disputes if d.get("status") == "overturned"),
    }
    return render(request, "pages/dispute.html", ctx)


@router.post("")
async def file_dispute(
    request: Request,
    dispute_type: str = Form(...),
    target_id: str = Form(...),
    reason: str = Form(...),
):
    """Employee files a dispute against an AI decision."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse("/disputes?msg=请先登录", status_code=303)

    employee_id = user.get("employee_id", "") or user.get("id", "")

    try:
        from app.safety.dispute import DisputeCenter
        center = DisputeCenter.get_instance()
        dispute = await center.file_dispute(
            employee_id=employee_id,
            dispute_type=dispute_type,
            target_id=target_id,
            reason=reason,
        )
        return RedirectResponse(f"/disputes/{dispute['id']}?msg=申诉已提交", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/disputes?msg=提交失败: {e}", status_code=303)


@router.post("/{dispute_id}/evidence")
async def add_evidence(
    request: Request,
    dispute_id: str,
    content: str = Form(...),
    evidence_type: str = Form("text"),
):
    """Add evidence to an existing dispute."""
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(f"/disputes/{dispute_id}?msg=请先登录", status_code=303)

    try:
        from app.safety.dispute import DisputeCenter
        center = DisputeCenter.get_instance()
        await center.add_evidence(dispute_id, {
            "type": evidence_type,
            "content": content,
            "submitted_by": (user or {}).get("id", "unknown"),
        })
        return RedirectResponse(f"/disputes/{dispute_id}?msg=证据已添加", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/disputes/{dispute_id}?msg=添加失败: {e}", status_code=303)


@router.post("/{dispute_id}/resolve")
async def resolve_dispute(
    request: Request,
    dispute_id: str,
    resolution: str = Form(...),
):
    db = Database.get_instance()
    dispute = db.get_by_id("disputes", dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    user = getattr(request.state, "user", {})
    db.update("disputes", dispute_id, {
        "status": DisputeStatus.RESOLVED.value,
        "resolution": resolution,
        "resolver_id": user.get("id", ""),
        "resolved_at": datetime.utcnow().isoformat(),
    })
    return RedirectResponse("/disputes", status_code=302)


@router.post("/{dispute_id}/overturn")
async def overturn_dispute(
    request: Request,
    dispute_id: str,
    resolution: str = Form(...),
    rule_correction: str = Form(""),
):
    db = Database.get_instance()
    dispute = db.get_by_id("disputes", dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    user = getattr(request.state, "user", {})
    db.update("disputes", dispute_id, {
        "status": DisputeStatus.OVERTURNED.value,
        "resolution": resolution,
        "rule_correction_suggestion": rule_correction,
        "resolver_id": user.get("id", ""),
        "resolved_at": datetime.utcnow().isoformat(),
    })
    return RedirectResponse("/disputes", status_code=302)
