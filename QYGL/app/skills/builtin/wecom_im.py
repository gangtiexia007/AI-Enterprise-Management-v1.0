"""F13 WeCom IM Skill — send messages and cards via WeCom Bot API.

Tools:
    wecom_im__send_message — send text message
    wecom_im__send_card    — send markdown card

Uses wecom-aibot-python-sdk when available, falls back to raw HTTP.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.enums import PermissionLevel
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)


def _get_bot_webhook(team_id: str) -> str:
    """Retrieve the WeCom bot webhook URL for the team."""
    from app.channels.bot_manager import BotManager
    manager = BotManager.get_instance()
    creds = manager.get_credentials(team_id, "wecom")
    return creds.get("webhook_url", "")


async def _send_wecom_message(
    team_id: str,
    recipient_id: str,
    content: str,
    msg_type: str = "text",
) -> dict[str, Any]:
    """Internal helper for sending a WeCom message."""
    webhook_url = _get_bot_webhook(team_id)
    if not webhook_url:
        return {"sent": False, "error": "No WeCom webhook configured"}

    if msg_type == "markdown":
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }
    else:
        mention = f"<@{recipient_id}> " if recipient_id else ""
        payload = {
            "msgtype": "text",
            "text": {"content": f"{mention}{content}", "mentioned_list": [recipient_id] if recipient_id else []},
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode", 0) != 0:
                return {"sent": False, "error": data.get("errmsg", "Unknown error")}
            return {"sent": True}
    except httpx.HTTPError as exc:
        logger.error("WeCom send failed: %s", exc)
        return {"sent": False, "error": str(exc)}


@tool(permission=PermissionLevel.P1, description="Send a text message via WeCom")
async def wecom_im__send_message(
    ctx: ToolContext,
    *,
    recipient_id: str = "",
    content: str,
) -> dict[str, Any]:
    """Send a text message through the WeCom bot webhook."""
    return await _send_wecom_message(ctx.team_id, recipient_id, content, "text")


@tool(permission=PermissionLevel.P1, description="Send a markdown card via WeCom")
async def wecom_im__send_card(
    ctx: ToolContext,
    *,
    content: str,
    recipient_id: str = "",
) -> dict[str, Any]:
    """Send a markdown-formatted card via WeCom."""
    return await _send_wecom_message(ctx.team_id, recipient_id, content, "markdown")
