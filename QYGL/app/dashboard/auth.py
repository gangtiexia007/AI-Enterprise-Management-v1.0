"""F36: Authentication — login/logout, bcrypt hashing, signed cookies, tier access."""

from __future__ import annotations

import logging
import os
from datetime import datetime

import bcrypt
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.core.database import Database, new_id
from app.core.enums import UserTier
from app.dashboard.app import templates, _global_context, render

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])

SECRET_KEY = os.getenv("QFBJ_SECRET_KEY", "qfbj-dashboard-secret-change-in-production")
SESSION_MAX_AGE = 86400 * 7
COOKIE_NAME = "qfbj_session"

_signer = URLSafeTimedSerializer(SECRET_KEY)

PUBLIC_PATHS = {"/login", "/logout", "/favicon.ico", "/health"}
WIZARD_PREFIX = "/wizard"
STATIC_PREFIX = "/static"
WS_PREFIX = "/ws"
WEBHOOK_PREFIX = "/webhook"

T2_ALLOWED_PREFIXES = {
    "/",
    "/teams",
    "/employees",
    "/tasks",
    "/approvals",
    "/kpi",
    "/escalations",
    "/disputes",
    "/hiring",
    "/customers",
    "/decisions",
    "/knowledge",
    "/memory",
    "/models",
    "/salary",
    "/commands",
    "/uploads",
    "/api",
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session_token(user_id: str) -> str:
    return _signer.dumps({"uid": user_id})


def decode_session_token(token: str) -> dict | None:
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> dict | None:
    return getattr(request.state, "user", None)


def ensure_admin_user() -> None:
    """Create default admin/admin123 on first run if no users exist."""
    db = Database.get_instance()
    users = db.query("dashboard_users", limit=1)
    if not users:
        db.insert("dashboard_users", {
            "id": new_id(),
            "username": "admin",
            "password_hash": hash_password("admin123"),
            "tier": UserTier.T1.value,
            "display_name": "管理员",
            "department": "",
            "employee_id": "",
        })
        logger.info("Default admin user created (admin/admin123)")


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if (
        path in PUBLIC_PATHS
        or path.startswith(WIZARD_PREFIX)
        or path.startswith(STATIC_PREFIX)
        or path.startswith(WS_PREFIX)
        or path.startswith(WEBHOOK_PREFIX)
    ):
        request.state.user = None
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return RedirectResponse("/login", status_code=302)

    payload = decode_session_token(token)
    if not payload:
        resp = RedirectResponse("/login", status_code=302)
        resp.delete_cookie(COOKIE_NAME)
        return resp

    db = Database.get_instance()
    user = db.get_by_id("dashboard_users", payload["uid"])
    if not user:
        resp = RedirectResponse("/login", status_code=302)
        resp.delete_cookie(COOKIE_NAME)
        return resp

    if user.get("tier") == UserTier.T3:
        if not path.startswith("/my"):
            return HTMLResponse("无仪表盘访问权限 (T3)", status_code=403)

    if user.get("tier") == UserTier.T2:
        allowed = any(path == p or path.startswith(p + "/") for p in T2_ALLOWED_PREFIXES)
        if not allowed:
            return HTMLResponse("权限不足", status_code=403)

    request.state.user = user
    # T2/T3 data scope: team ids from linked employee row; T1 = full company (no filter).
    if user.get("tier") == UserTier.T1:
        request.state.user_teams = None
    elif user.get("tier") in (UserTier.T2, UserTier.T3):
        emp_id = (user.get("employee_id") or "").strip()
        if not emp_id:
            request.state.user_teams = []
        else:
            emp_row = db.get_by_id("employees", emp_id)
            tid = (emp_row or {}).get("team_id") or ""
            request.state.user_teams = [tid] if tid else []
    else:
        request.state.user_teams = None

    return await call_next(request)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    ctx = _global_context(request)
    ctx["error"] = ""
    return render(request, "login.html", ctx)


@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    db = Database.get_instance()
    rows = db.query("dashboard_users", {"username": username}, limit=1)

    if not rows or not verify_password(password, rows[0]["password_hash"]):
        ctx = _global_context(request)
        ctx["error"] = "用户名或密码错误"
        return render(request, "login.html", ctx, status_code=401)

    user = rows[0]
    token = create_session_token(user["id"])
    next_url = "/my" if user.get("tier") == UserTier.T3 else "/"
    resp = RedirectResponse(next_url, status_code=302)
    resp.set_cookie(COOKIE_NAME, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp
