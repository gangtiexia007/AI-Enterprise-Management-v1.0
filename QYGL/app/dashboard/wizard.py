"""F36: Setup Wizard — 3-step guided configuration for first-time setup.

Steps:
1. Company name (basic info)
2. Configure LLM (API key + test connection)
3. Configure Feishu Bot (App ID + Secret)

On completion: auto-creates Boss Agent + binds the Feishu bot to it.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.core.team_registry import TeamRegistry
from app.dashboard.app import _global_context, render
from app.dashboard.auth import COOKIE_NAME, decode_session_token

logger = logging.getLogger(__name__)

WIZARD_COMPLETE_MSG = "初始配置已完成，Boss Agent 已创建。欢迎使用千方百计AI！"


def _post_wizard_redirect_url(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = decode_session_token(token)
        if payload:
            user = Database.get_instance().get_by_id("dashboard_users", payload.get("uid", ""))
            if user:
                q = quote(WIZARD_COMPLETE_MSG)
                return f"/?msg={q}"
    q = quote(WIZARD_COMPLETE_MSG)
    return f"/login?msg={q}"


router = APIRouter(tags=["wizard"])


# ── Step 1: Company Info ─────────────────────────────────────────────

@router.get("/step1", response_class=HTMLResponse)
async def step1(request: Request):
    ctx = _global_context(request)
    ctx["current_step"] = 1
    ctx["total_steps"] = 3
    return render(request, "wizard/step1.html", ctx)


@router.post("/step1")
async def step1_save(request: Request, company_name: str = Form("")):
    resp = RedirectResponse("/wizard/step2", status_code=302)
    resp.set_cookie("wizard_company_name", company_name, httponly=True)
    return resp


# ── Step 2: LLM Configuration ───────────────────────────────────────

@router.get("/step2", response_class=HTMLResponse)
async def step2(request: Request):
    ctx = _global_context(request)
    ctx["current_step"] = 2
    ctx["total_steps"] = 3
    db = Database.get_instance()
    ctx["models"] = db.query("models", limit=50)
    return render(request, "wizard/step2.html", ctx)


@router.post("/step2")
async def step2_save(
    request: Request,
    model_name: str = Form(""),
    provider: str = Form(""),
    api_key: str = Form(""),
):
    db = Database.get_instance()
    if model_name and provider:
        from app.core.security import encrypt
        existing = db.query("models", {"name": model_name}, limit=1)
        if not existing:
            db.insert("models", {
                "id": new_id(),
                "name": model_name,
                "provider": provider,
                "api_key_encrypted": encrypt(api_key) if api_key else "",
                "is_default": True,
                "enabled": True,
            })
    return RedirectResponse("/wizard/step3", status_code=302)


# ── Step 3: Feishu Bot + Auto-complete ───────────────────────────────

@router.get("/step3", response_class=HTMLResponse)
async def step3(request: Request):
    ctx = _global_context(request)
    ctx["current_step"] = 3
    ctx["total_steps"] = 3
    return render(request, "wizard/step3.html", ctx)


@router.post("/step3")
async def step3_save(
    request: Request,
    channel: str = Form("feishu"),
    app_id: str = Form(""),
    app_secret: str = Form(""),
):
    company_name = request.cookies.get("wizard_company_name", "")
    db = Database.get_instance()

    registry = TeamRegistry(db)
    boss_team = registry.create_boss_agent(company_name=company_name)
    boss_team_id = boss_team["id"]

    if app_id:
        from app.core.security import encrypt
        existing_bot = db.query("team_bots", {"team_id": boss_team_id, "channel": channel}, limit=1)
        if existing_bot:
            db.update("team_bots", existing_bot[0]["id"], {
                "app_id_encrypted": encrypt(app_id),
                "app_secret_encrypted": encrypt(app_secret) if app_secret else "",
                "enabled": True,
            })
        else:
            db.insert("team_bots", {
                "id": new_id(),
                "team_id": boss_team_id,
                "channel": channel,
                "app_id_encrypted": encrypt(app_id),
                "app_secret_encrypted": encrypt(app_secret) if app_secret else "",
                "webhook_url": "",
                "enabled": True,
                "verified": False,
            })

    target = _post_wizard_redirect_url(request)
    resp = RedirectResponse(target, status_code=302)
    resp.delete_cookie("wizard_company_name")
    return resp
