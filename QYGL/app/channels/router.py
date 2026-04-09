"""F22: Unified Inbound Message Router.

Converts platform-specific messages into ``UnifiedMessage`` and routes them
to the correct Agent Team based on the ``bot_id → team_id`` mapping.

Also registers webhook routes on the FastAPI app.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from fastapi import FastAPI

from app.core.enums import Channel
from app.core.models import UnifiedMessage

logger = logging.getLogger(__name__)

InboundHandler = Callable[[UnifiedMessage], Coroutine[Any, Any, str | None]]

_inbound_handler: InboundHandler | None = None


def set_inbound_handler(handler: InboundHandler) -> None:
    """Set the global inbound message handler (normally the Agent Loop)."""
    global _inbound_handler
    _inbound_handler = handler


async def route_inbound_message(msg: UnifiedMessage) -> str | None:
    """Route a ``UnifiedMessage`` to the appropriate team.

    Steps:
    1. Identify the team from bot_id / sender_id.
    2. Identify the employee from channel-specific sender_id.
    3. Hand off to the registered inbound handler (Agent Loop).

    Returns assistant reply text from the handler, if any.
    """
    if not msg.team_id:
        msg.team_id = _resolve_team(msg)

    if not msg.employee_id and msg.sender_id:
        msg.employee_id = _resolve_employee(msg)

    if not msg.team_id:
        logger.warning("Cannot route message: no team resolved for sender %s", msg.sender_id)
        return None

    logger.info(
        "Routing message: channel=%s team=%s employee=%s type=%s",
        msg.channel, msg.team_id, msg.employee_id, msg.msg_type,
    )

    if _inbound_handler:
        return await _inbound_handler(msg)
    logger.warning("No inbound handler registered; message dropped")
    return None


def _resolve_team(msg: UnifiedMessage) -> str:
    """Look up team_id from the bot routing table or sender mapping."""
    from app.channels.bot_manager import BotManager
    manager = BotManager.get_instance()

    bot_id = msg.raw.get("bot_id", "")
    if bot_id:
        team_id = manager.route_bot_to_team(bot_id)
        if team_id:
            return team_id

    if msg.channel == Channel.FEISHU:
        app_id = (msg.raw or {}).get("app_id", "")
        if app_id:
            tid = manager.route_feishu_app_id_to_team(app_id)
            if tid:
                return tid
        from app.core.database import Database
        db = Database.get_instance()
        if msg.sender_id:
            employees = db.query("employees", {"feishu_id": msg.sender_id}, limit=1)
            if employees:
                return employees[0].get("team_id", "")
    elif msg.channel == Channel.WECOM:
        from app.core.database import Database
        db = Database.get_instance()
        if msg.sender_id:
            employees = db.query("employees", {"wecom_id": msg.sender_id}, limit=1)
            if employees:
                return employees[0].get("team_id", "")

    return ""


def _resolve_employee(msg: UnifiedMessage) -> str:
    """Look up employee_id from the sender_id."""
    from app.core.employee_manager import EmployeeManager
    em = EmployeeManager()
    emp = em.identify_by_sender(msg.channel, msg.sender_id)
    if emp:
        return emp.get("id", "")
    return ""


# ── FastAPI Route Registration ────────────────────────────────────────


def register_webhook_routes(app: FastAPI) -> None:
    """Mount channel-specific webhook endpoints on the FastAPI application."""
    from app.channels.feishu import handle_feishu_event

    @app.post("/webhook/feishu")
    async def feishu_webhook(request):
        from fastapi import Request
        return await handle_feishu_event(request)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "qfbj-channels"}

    logger.info("Webhook routes registered: /webhook/feishu, /health")


async def send_reply(channel: str, team_id: str, content: str, extra: dict | None = None) -> bool:
    """Send a reply message through the appropriate channel."""
    if channel == Channel.FEISHU:
        logger.warning("Feishu outbound reply not yet implemented (send_feishu_message missing)")
        return False

    if channel == Channel.WECOM:
        try:
            from app.channels.wecom import WeComManager
            mgr = WeComManager.get_instance()
            return await mgr.send_to_team(team_id, content)
        except Exception as e:
            logger.warning("WeCom reply failed: %s", e)
        return False

    return False
