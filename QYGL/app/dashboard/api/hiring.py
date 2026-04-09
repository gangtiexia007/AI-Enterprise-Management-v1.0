"""F40: Hiring management — profiles, candidates, status workflow."""

from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.dashboard.app import _global_context, get_user_team_filter, render

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hiring"])

_CANDIDATE_STATUSES = frozenset(
    {"pending", "screening", "interview", "scored", "offered", "hired", "rejected"}
)


@router.get("/hiring", response_class=HTMLResponse)
async def hiring_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)
    user_teams = get_user_team_filter(request)

    profiles = db.query("hiring_profiles", order_by="created_at DESC", limit=100)
    candidates = db.query("candidates", order_by="created_at DESC", limit=200)
    teams = db.query("teams", order_by="name", limit=100)

    if user_teams is not None:
        profiles = [p for p in profiles if p.get("team_id") in user_teams]
        candidates = [c for c in candidates if c.get("team_id") in user_teams]
        teams = [t for t in teams if t["id"] in user_teams]

    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in teams}

    ctx.update(
        {
            "profiles": profiles,
            "candidates": candidates,
            "teams": teams,
            "team_map": team_map,
            "stats": {
                "total_profiles": len(profiles),
                "total_candidates": len(candidates),
                "pending_interview": sum(
                    1 for c in candidates if c.get("status") in ("screening", "interview")
                ),
                "hired": sum(1 for c in candidates if c.get("status") == "hired"),
            },
        }
    )

    return render(request, "pages/hiring.html", ctx)


@router.post("/hiring/profile")
async def create_hiring_profile(
    request: Request,
    team_id: str = Form(...),
    source: str = Form("manual"),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    if user_teams is not None and team_id not in user_teams:
        raise HTTPException(status_code=403, detail="无权为该团队创建招聘画像")

    from app.engines.hiring import HiringEngine

    engine = HiringEngine(db=db)
    engine.create_hiring_profile(team_id=team_id, source=source)

    return RedirectResponse("/hiring?msg=" + quote("招聘画像创建成功"), status_code=302)


@router.get("/hiring/candidates/{profile_id}", response_class=HTMLResponse)
async def candidates_for_profile(request: Request, profile_id: str):
    db = Database.get_instance()
    profile = db.get_by_id("hiring_profiles", profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    user_teams = get_user_team_filter(request)
    if user_teams is not None and profile.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Profile not found")

    candidates = db.query(
        "candidates", {"team_id": profile["team_id"]}, order_by="created_at DESC"
    )
    teams = db.query("teams", order_by="name", limit=100)
    team_map = {t["id"]: (t.get("display_name") or t.get("name") or t["id"]) for t in teams}

    ctx = _global_context(request)
    ctx.update(
        {
            "profiles": [profile],
            "candidates": candidates,
            "teams": teams,
            "team_map": team_map,
            "stats": {
                "total_profiles": 1,
                "total_candidates": len(candidates),
                "pending_interview": sum(
                    1 for c in candidates if c.get("status") in ("screening", "interview")
                ),
                "hired": sum(1 for c in candidates if c.get("status") == "hired"),
            },
        }
    )
    return render(request, "pages/hiring.html", ctx)


@router.post("/hiring/candidate")
async def add_candidate(
    request: Request,
    name: str = Form(...),
    team_id: str = Form(...),
    position: str = Form(""),
    resume_summary: str = Form(""),
):
    db = Database.get_instance()
    user_teams = get_user_team_filter(request)
    if user_teams is not None and team_id not in user_teams:
        raise HTTPException(status_code=403, detail="无权为该团队添加候选人")

    candidate = {
        "id": new_id(),
        "team_id": team_id,
        "name": name,
        "position": position,
        "resume_summary": resume_summary,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    db.insert("candidates", candidate)

    return RedirectResponse("/hiring?msg=" + quote("候选人添加成功"), status_code=302)


@router.post("/hiring/candidate/{candidate_id}/status")
async def update_candidate_status(
    request: Request,
    candidate_id: str,
    status: str = Form(...),
):
    if status not in _CANDIDATE_STATUSES:
        raise HTTPException(status_code=400, detail="无效状态")

    db = Database.get_instance()
    candidate = db.get_by_id("candidates", candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    user_teams = get_user_team_filter(request)
    if user_teams is not None and candidate.get("team_id") not in user_teams:
        raise HTTPException(status_code=404, detail="Candidate not found")

    db.update("candidates", candidate_id, {"status": status})

    return RedirectResponse("/hiring?msg=" + quote("状态已更新"), status_code=302)
