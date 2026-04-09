"""F36: Dashboard application — route registration, Jinja2 setup, global context."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request

from app.core.enums import UserTier
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.dashboard.ui_labels import register_jinja_filters

logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["basename"] = lambda p: os.path.basename((p or "").replace("\\", "/"))
register_jinja_filters(templates.env)


def get_user_team_filter(request: Request) -> list[str] | None:
    """Return team ids for T2 users, or None for T1 (all teams, no filter)."""
    return getattr(request.state, "user_teams", None)


def render(
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Starlette 1.0 compatible template rendering."""
    ctx = context or {}
    ctx["request"] = request
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=ctx,
        status_code=status_code,
    )

MY_PORTAL_NAV = [
    {
        "group": "我的工作台",
        "links": [
            {"label": "首页", "url": "/my", "icon": "home"},
            {"label": "我的任务", "url": "/my/tasks", "icon": "clipboard"},
            {"label": "我的 KPI", "url": "/my/kpi", "icon": "bar-chart-2"},
        ],
    },
]

NAV_ITEMS = [
    {
        "group": "",
        "links": [
            {"label": "总览", "url": "/", "icon": "home"},
        ],
    },
    {
        "group": "组织管理",
        "links": [
            {"label": "团队管理", "url": "/teams", "icon": "users"},
            {"label": "员工管理", "url": "/employees", "icon": "user"},
            {"label": "客户管理", "url": "/customers", "icon": "heart"},
        ],
    },
    {
        "group": "任务执行",
        "links": [
            {"label": "任务中心", "url": "/tasks", "icon": "clipboard"},
            {"label": "审批中心", "url": "/approvals", "icon": "check-circle"},
            {"label": "绩效管理", "url": "/kpi", "icon": "bar-chart-2"},
        ],
    },
    {
        "group": "知识与技能",
        "links": [
            {"label": "知识库", "url": "/knowledge", "icon": "book-open"},
            {"label": "快捷指令", "url": "/commands", "icon": "terminal"},
        ],
    },
    {
        "group": "系统",
        "links": [
            {"label": "模型管理", "url": "/models", "icon": "cpu"},
            {"label": "决策日志", "url": "/decisions", "icon": "book-open"},
        ],
    },
]


def _global_context(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    current_path = request.url.path
    nav = NAV_ITEMS
    if user and user.get("tier") == UserTier.T3.value:
        nav = MY_PORTAL_NAV
    return {
        "request": request,
        "current_user": user,
        "user_teams": getattr(request.state, "user_teams", None),
        "nav_items": nav,
        "current_path": current_path,
    }


def register_dashboard_routes(app: FastAPI) -> None:
    """Register dashboard routes. Called from main.py create_app().

    NOTE: Middleware and routes are now registered directly in main.py
    to avoid the 'Cannot add middleware after startup' error.
    This function is kept for backward compatibility and static file mounting.
    """
    if STATIC_DIR.exists():
        try:
            app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        except Exception:
            pass
    logger.info("Dashboard static files mounted (%d nav groups)", len(NAV_ITEMS))
