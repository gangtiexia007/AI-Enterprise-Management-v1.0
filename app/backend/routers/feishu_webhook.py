"""
Feishu Webhook receiver — handles event push from Feishu Open Platform.

Supported events:
  - url_verification  (initial handshake)
  - im.message.receive_v1  (DM or group message sent to bot)

Flow:
  Feishu sends POST → challenge / message extracted → AgentLoop → reply via send_to_chat
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory dedup (event_id → timestamp)
_SEEN_EVENTS: dict[str, float] = {}
_DEDUP_TTL = 300


def _dedup(event_id: str) -> bool:
    """Return True if this event_id was already processed."""
    now = time.time()
    # Prune old entries
    expired = [k for k, ts in _SEEN_EVENTS.items() if now - ts > _DEDUP_TTL]
    for k in expired:
        _SEEN_EVENTS.pop(k, None)
    if event_id in _SEEN_EVENTS:
        return True
    _SEEN_EVENTS[event_id] = now
    return False


def _verify_signature(body_bytes: bytes, timestamp: str, nonce: str, signature: str) -> bool:
    """Verify Feishu request signature (optional — requires encrypt_key configured in Feishu)."""
    from database import SessionLocal
    from models import Setting

    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == "feishu_encrypt_key").first()
        key = s.value if s else ""
    finally:
        db.close()
    if not key:
        return True  # No key configured — skip verification
    content = timestamp + nonce + key + body_bytes.decode("utf-8", errors="replace")
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@router.post("/webhook")
async def feishu_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_lark_signature: Optional[str] = Header(None, alias="X-Lark-Signature"),
    x_lark_request_timestamp: Optional[str] = Header(None, alias="X-Lark-Request-Timestamp"),
    x_lark_request_nonce: Optional[str] = Header(None, alias="X-Lark-Request-Nonce"),
):
    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except Exception:
        return Response(content='{"code":1,"msg":"invalid json"}', media_type="application/json")

    # ── Challenge verification ──────────────────────────────────────────────
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge", "")}

    # ── Signature check (if key configured) ────────────────────────────────
    if x_lark_signature:
        if not _verify_signature(
            body_bytes,
            x_lark_request_timestamp or "",
            x_lark_request_nonce or "",
            x_lark_signature,
        ):
            logger.warning("Feishu webhook signature mismatch")
            return Response(content='{"code":1,"msg":"sig error"}', media_type="application/json")

    header = body.get("header", {})
    event_type = header.get("event_type", "")
    event_id = header.get("event_id", "")

    # Dedup
    if event_id and _dedup(event_id):
        return {"code": 0, "msg": "duplicate"}

    # ── Route events ────────────────────────────────────────────────────────
    if event_type == "im.message.receive_v1":
        background_tasks.add_task(_handle_message, body)

    # Always return 200 immediately so Feishu doesn't retry
    return {"code": 0}


async def _handle_message(body: dict) -> None:
    """Process incoming chat message in background and reply via Feishu."""
    event = body.get("event") or {}
    msg = event.get("message") or {}
    sender = event.get("sender") or {}

    msg_type = msg.get("message_type", "")
    chat_id = msg.get("chat_id", "")
    chat_type = msg.get("chat_type", "p2p")  # p2p or group

    # Only handle text for now
    if msg_type != "text":
        logger.debug(f"Feishu webhook: skipping msg_type={msg_type}")
        return

    try:
        content_raw = msg.get("content", "{}")
        content = json.loads(content_raw)
        text = (content.get("text") or "").strip()
    except Exception:
        return

    if not text:
        return

    # Strip @mentions in group chat
    import re
    text = re.sub(r"@\S+", "", text).strip()
    if not text:
        return

    sender_id = (sender.get("sender_id") or {})
    sender_union_id = sender_id.get("union_id") or ""

    logger.info(f"Feishu message from={sender_union_id} chat={chat_id}: {text[:80]}")

    # Process via AgentLoop
    from database import SessionLocal
    from models import Conversation, AuditLog
    from datetime import datetime

    db = SessionLocal()
    try:
        db.add(Conversation(role="user", content=f"[飞书] {text}", created_at=datetime.utcnow()))
        db.commit()

        from harness.agent_loop import AgentLoop
        loop = AgentLoop()
        reply = await loop.run(text, db_session=db, agent_mode="full")

        db.add(Conversation(role="assistant", content=reply, created_at=datetime.utcnow()))
        db.add(AuditLog(
            action="feishu_chat",
            detail=f"from={sender_union_id} chat_type={chat_type} input={text[:100]}",
            actor="feishu_bot",
            resource_type="conversation",
            created_at=datetime.utcnow(),
        ))
        db.commit()
    except Exception as e:
        logger.error(f"AgentLoop error in feishu webhook: {e}")
        reply = f"抱歉，处理您的消息时出现错误：{e}"
    finally:
        db.close()

    # Send reply to chat
    from harness.feishu_client import feishu_client
    sent = feishu_client.send_text_to_chat(chat_id, reply)
    if not sent:
        logger.error(f"Failed to send reply to chat_id={chat_id}")
