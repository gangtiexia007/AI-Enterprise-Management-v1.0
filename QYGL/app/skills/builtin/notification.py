"""F13 Notification Skill — abstract notification routing and smart merge.

Tools:
    notification__send           — send a single notification
    notification__send_card      — send an interactive card message
    notification__merge_and_send — smart merge (important=immediate, normal=5min batch)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from app.core.enums import Channel, PermissionLevel
from app.core.events import Events
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

MERGE_WINDOW_S = 300
_pending_normal: dict[str, list[dict[str, Any]]] = defaultdict(list)
_pending_lock = asyncio.Lock() if asyncio else None
_last_flush_ts: float = 0.0


def _resolve_channel(ctx: ToolContext, channel: str = "") -> str:
    """Determine the delivery channel from explicit arg or team bot config."""
    if channel:
        return channel
    from app.core.database import Database
    db = Database.get_instance()
    if ctx.team_id:
        bots = db.query("team_bots", {"team_id": ctx.team_id, "enabled": True}, limit=1)
        if bots:
            return bots[0].get("channel", Channel.FEISHU)
    return Channel.FEISHU


async def _dispatch(
    channel: str,
    recipient_id: str,
    content: str,
    msg_type: str = "text",
    card_json: dict[str, Any] | None = None,
    team_id: str = "",
) -> dict[str, Any]:
    """Route to the appropriate channel sender."""
    if channel == Channel.FEISHU:
        from app.skills.builtin.feishu_im import _send_feishu_message
        return await _send_feishu_message(team_id, recipient_id, content, msg_type, card_json)
    elif channel == Channel.WECOM:
        from app.skills.builtin.wecom_im import _send_wecom_message
        return await _send_wecom_message(team_id, recipient_id, content, msg_type)
    else:
        logger.warning("Unsupported channel: %s", channel)
        return {"error": f"Unsupported channel: {channel}"}


@tool(permission=PermissionLevel.P1, description="Send a notification to a recipient via the appropriate channel")
async def notification__send(
    ctx: ToolContext,
    *,
    recipient_id: str,
    content: str,
    channel: str = "",
    msg_type: str = "text",
) -> dict[str, Any]:
    """Send a single notification message, routing to feishu/wecom automatically."""
    resolved_channel = _resolve_channel(ctx, channel)
    result = await _dispatch(resolved_channel, recipient_id, content, msg_type, team_id=ctx.team_id)

    _emit_notification_event(ctx, recipient_id, resolved_channel, content)

    return {"channel": resolved_channel, "recipient": recipient_id, **result}


@tool(permission=PermissionLevel.P1, description="Send an interactive card message")
async def notification__send_card(
    ctx: ToolContext,
    *,
    recipient_id: str,
    card_json: dict[str, Any],
    channel: str = "",
) -> dict[str, Any]:
    """Send a rich interactive card notification."""
    resolved_channel = _resolve_channel(ctx, channel)
    result = await _dispatch(
        resolved_channel, recipient_id, "", "card", card_json, team_id=ctx.team_id,
    )
    _emit_notification_event(ctx, recipient_id, resolved_channel, "[card]")
    return {"channel": resolved_channel, "recipient": recipient_id, **result}


@tool(permission=PermissionLevel.P1, description="Smart merge: important=immediate, normal=5min batch")
async def notification__merge_and_send(
    ctx: ToolContext,
    *,
    recipient_id: str,
    content: str,
    important: bool = False,
    channel: str = "",
) -> dict[str, Any]:
    """Smart notification merging.

    * **important** messages are sent immediately.
    * **normal** messages are buffered and merged within a 5-minute window.
    """
    resolved_channel = _resolve_channel(ctx, channel)

    if important:
        result = await _dispatch(resolved_channel, recipient_id, content, team_id=ctx.team_id)
        _emit_notification_event(ctx, recipient_id, resolved_channel, content)
        return {"sent": True, "immediate": True, **result}

    key = f"{resolved_channel}:{recipient_id}"
    _pending_normal[key].append({
        "content": content,
        "team_id": ctx.team_id,
        "timestamp": time.time(),
    })

    global _last_flush_ts
    now = time.time()
    if now - _last_flush_ts >= MERGE_WINDOW_S:
        flushed = await _flush_pending()
        _last_flush_ts = now
        return {"sent": True, "merged": True, "flushed_count": flushed}

    return {"queued": True, "pending_count": len(_pending_normal[key])}


async def _flush_pending() -> int:
    """Flush all pending normal notifications as merged messages."""
    count = 0
    keys = list(_pending_normal.keys())
    for key in keys:
        items = _pending_normal.pop(key, [])
        if not items:
            continue
        channel, recipient_id = key.split(":", 1)
        merged_content = "\n---\n".join(item["content"] for item in items)
        header = f"📋 {len(items)} 条合并通知:\n\n"
        team_id = items[0].get("team_id", "")
        await _dispatch(channel, recipient_id, header + merged_content, team_id=team_id)
        count += len(items)
    return count


def _emit_notification_event(
    ctx: ToolContext,
    recipient_id: str,
    channel: str,
    content_preview: str,
) -> None:
    try:
        from app.infra.eventbus import EventBus
        bus = EventBus.get_instance()
        bus.emit_nowait(Events.NOTIFICATION_SENT, {
            "team_id": ctx.team_id,
            "recipient_id": recipient_id,
            "channel": channel,
            "preview": content_preview[:100],
        })
    except Exception:
        pass
