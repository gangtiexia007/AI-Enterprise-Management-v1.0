"""F38: WebSocket endpoint — real-time chat streaming with smart panel data."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import Database
from app.core.enums import Channel, UserTier
from app.core.models import UnifiedMessage
from app.dashboard.auth import COOKIE_NAME, decode_session_token
from app.runtime.agent_loop import AgentLoop

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

ENTITY_KEYWORDS = {
    "employee": ["员工", "人员", "成员", "staff"],
    "kpi": ["KPI", "绩效", "考核", "指标"],
    "task": ["任务", "工作", "待办"],
    "team": ["团队", "部门", "小组"],
}


def _detect_panel_context(text: str) -> dict | None:
    """Detect if user message mentions entities that warrant smart panel data."""
    db = Database.get_instance()

    for entity_type, keywords in ENTITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return _build_panel_data(db, entity_type, text)
    return None


def _build_panel_data(db: Database, entity_type: str, query: str) -> dict:
    if entity_type == "employee":
        employees = db.query("employees", limit=5)
        return {"type": "employee_panel", "data": employees}
    elif entity_type == "kpi":
        kpis = db.query("kpi_definitions", limit=5)
        return {"type": "kpi_panel", "data": kpis}
    elif entity_type == "task":
        tasks = db.query("tasks", {"status": "pending"}, limit=5)
        return {"type": "task_panel", "data": tasks}
    elif entity_type == "team":
        teams = db.query("teams", limit=5)
        return {"type": "team_panel", "data": teams}
    return {"type": "default_panel", "data": {}}


def _build_default_panel(db: Database) -> dict:
    """Build the 4-dimension overview panel."""
    return {
        "type": "overview_panel",
        "data": {
            "pending_approvals": db.count("approval_requests", {"status": "pending"}),
            "active_tasks": db.count("tasks", {"status": "in_progress"}),
            "active_teams": db.count("teams", {"status": "active"}) + db.count("teams", {"status": "live"}),
            "open_disputes": db.count("disputes", {"status": "filed"}),
        },
    }


def _ws_user_can_access_team(user: dict[str, Any] | None, team_id: str) -> bool:
    if not user:
        return False
    if user.get("tier") == UserTier.T1.value:
        return True
    teams = user.get("_ws_teams") or []
    return team_id in teams


def _resolve_ws_user(db: Database, websocket: WebSocket) -> dict[str, Any] | None:
    token = websocket.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = decode_session_token(token)
    if not payload:
        return None
    user = db.get_by_id("dashboard_users", payload.get("uid", ""))
    if not user:
        return None
    if user.get("tier") == UserTier.T1.value:
        user = dict(user)
        user["_ws_teams"] = None
        return user
    if user.get("tier") == UserTier.T3.value:
        emp_id = (user.get("employee_id") or "").strip()
        teams: list[str] = []
        if emp_id:
            emp_row = db.get_by_id("employees", emp_id)
            tid = (emp_row or {}).get("team_id") or ""
            if tid:
                teams = [tid]
        user = dict(user)
        user["_ws_teams"] = teams
        return user
    emp_id = (user.get("employee_id") or "").strip()
    teams: list[str] = []
    if emp_id:
        emp_row = db.get_by_id("employees", emp_id)
        tid = (emp_row or {}).get("team_id") or ""
        if tid:
            teams = [tid]
    user = dict(user)
    user["_ws_teams"] = teams
    return user


async def ws_chat_handler(websocket: WebSocket) -> None:
    await websocket.accept()

    db = Database.get_instance()
    user = _resolve_ws_user(db, websocket)
    if not user:
        await websocket.send_json({
            "type": "error",
            "message": "请先登录后台后再使用聊天。",
        })
        await websocket.close(code=4401)
        return

    try:
        init = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.warning("WebSocket init failed: %s", exc)
        await websocket.close(code=4400)
        return

    team_id = (init.get("team_id") or "").strip()
    if not team_id:
        await websocket.send_json({"type": "error", "message": "缺少 team_id。"})
        await websocket.close(code=4400)
        return

    if not _ws_user_can_access_team(user, team_id):
        await websocket.send_json({"type": "error", "message": "无权使用该团队的智能助手。"})
        await websocket.close(code=4403)
        return

    team = db.get_by_id("teams", team_id)
    if not team:
        await websocket.send_json({"type": "error", "message": "团队不存在。"})
        await websocket.close(code=4404)
        return

    emp_id = (user.get("employee_id") or "").strip()
    employee = db.get_by_id("employees", emp_id) if emp_id else None

    await websocket.send_json({
        "type": "panel",
        "panel": _build_default_panel(db),
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_text = (data.get("content") or "").strip()
            if not msg_text:
                continue

            panel = _detect_panel_context(msg_text)
            if panel:
                await websocket.send_json({"type": "panel", "panel": panel})

            await websocket.send_json({"type": "stream_start"})

            try:
                loop = AgentLoop(db=db)
                um = UnifiedMessage(
                    channel=Channel.DASHBOARD,
                    sender_id=user.get("id", "dashboard"),
                    team_id=team_id,
                    employee_id=emp_id,
                    content=msg_text,
                )
                agent_resp = await loop.run(
                    um,
                    team=team,
                    employee=employee,
                )
                response_text = agent_resp.content or ""
            except Exception as exc:
                logger.exception("WebSocket AgentLoop error: %s", exc)
                response_text = "抱歉，处理您的消息时遇到问题，请稍后重试。"

            chunk_size = 24
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i : i + chunk_size]
                await websocket.send_json({"type": "stream", "content": chunk})

            await websocket.send_json({"type": "stream_end"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await ws_chat_handler(websocket)
