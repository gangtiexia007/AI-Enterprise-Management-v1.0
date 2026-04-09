"""F23: Feishu Channel — webhook handler, signature verification, Bot API helpers.

Handles inbound Feishu event callbacks (messages, card actions) and provides
outbound helpers (send message, upload file, send card).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import httpx
from fastapi import Request, Response

from app.core.config import get_config
from app.core.enums import Channel, MessageType
from app.core.models import UnifiedMessage

logger = logging.getLogger(__name__)

_PROCESSED_EVENT_IDS: dict[str, float] = {}
_DEDUP_TTL = 300


def verify_signature(
    timestamp: str,
    nonce: str,
    body: bytes | str,
    encrypt_key: str,
    signature: str,
) -> bool:
    """Verify Feishu webhook callback signature (Encrypt Key strategy).

    Feishu computes SHA-256 over: utf8(timestamp + nonce + encrypt_key) + raw body bytes.
    """
    if isinstance(body, str):
        body_b = body.encode("utf-8")
    else:
        body_b = body
    prefix = (timestamp + nonce + encrypt_key).encode("utf-8")
    computed = hashlib.sha256(prefix + body_b).hexdigest()
    return computed == signature


def _dedup(event_id: str) -> bool:
    """Return True if this event_id was already processed recently."""
    now = time.time()
    cutoff = now - _DEDUP_TTL
    expired = [k for k, v in _PROCESSED_EVENT_IDS.items() if v < cutoff]
    for k in expired:
        _PROCESSED_EVENT_IDS.pop(k, None)

    if event_id in _PROCESSED_EVENT_IDS:
        return True
    _PROCESSED_EVENT_IDS[event_id] = now
    return False


async def handle_feishu_event(request: Request) -> Response:
    """FastAPI endpoint handler for Feishu event callbacks.

    Handles:
    * URL verification challenge
    * Message events (im.message.receive_v1)
    * Card action callbacks (card.action.trigger)
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    cfg = get_config()
    encrypt_key = (cfg.feishu_encrypt_key or "").strip()
    if encrypt_key:
        ts = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        sig = request.headers.get("X-Lark-Signature", "")
        if not verify_signature(ts, nonce, body_bytes, encrypt_key, sig):
            logger.warning("Feishu signature verification failed")
            return Response(content='{"error":"invalid signature"}', status_code=403)

    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        return Response(content='{"error":"invalid json"}', status_code=400)

    if "challenge" in payload:
        return Response(
            content=json.dumps({"challenge": payload["challenge"]}),
            media_type="application/json",
        )

    header = payload.get("header", {})
    event_id = header.get("event_id", "")
    if event_id and _dedup(event_id):
        return Response(content='{"ok":true}', status_code=200)

    event_type = header.get("event_type", "")
    event_data = payload.get("event", {})
    app_id = header.get("app_id", "")

    logger.info("Feishu event: type=%s id=%s", event_type, event_id)

    if event_type == "im.message.receive_v1":
        msg = _parse_message_event(event_data, app_id=app_id)
        if msg:
            if msg.file_url and msg.msg_type in (MessageType.FILE, MessageType.IMAGE):
                message_id = (msg.raw or {}).get("message_id", "")
                file_type = (msg.raw or {}).get("file_type", "file")
                download_team_id = msg.team_id
                if not download_team_id and app_id:
                    try:
                        from app.channels.bot_manager import BotManager
                        download_team_id = BotManager.get_instance().route_feishu_app_id_to_team(app_id) or ""
                    except Exception:
                        pass
                if message_id:
                    local_path = await download_feishu_file(
                        message_id=message_id,
                        file_key=msg.file_url,
                        file_type=file_type,
                        team_id=download_team_id,
                    )
                    if local_path:
                        msg.file_path = local_path
                        if not msg.file_name:
                            from pathlib import Path as _P
                            msg.file_name = _P(local_path).name

            reply = await _route_message(msg)
            if reply:
                await _send_feishu_reply(msg, reply)

    elif event_type == "card.action.trigger":
        await _handle_card_action(header, event_data)

    return Response(content='{"ok":true}', status_code=200)


async def download_feishu_file(message_id: str, file_key: str, file_type: str, team_id: str = "") -> str:
    """Download a file from Feishu and save to data/uploads/. Returns local file path."""
    from pathlib import Path
    from app.core.database import new_id

    if team_id:
        from app.skills.builtin import feishu_im as fim
        creds = fim._get_bot_credentials(team_id)
        token = await fim._get_tenant_access_token(creds.get("app_id", ""), creds.get("app_secret", ""))
    else:
        cfg = get_config()
        if not cfg.feishu_app_id:
            logger.warning("No Feishu credentials to download file")
            return ""
        from app.skills.builtin import feishu_im as fim
        token = await fim._get_tenant_access_token(cfg.feishu_app_id, cfg.feishu_app_secret)

    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
    params = {"type": file_type if file_type else "file"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            logger.warning("Failed to download Feishu file: %s %s", resp.status_code, resp.text[:200])
            return ""
        file_bytes = resp.content
        content_disp = resp.headers.get("Content-Disposition", "")

    uploads_dir = Path("data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    ext = ".dat"
    if "filename=" in content_disp:
        fname = content_disp.split("filename=")[-1].strip('" ')
        if "." in fname:
            ext = "." + fname.rsplit(".", 1)[-1]
    elif file_type == "image":
        ext = ".png"

    file_id = new_id()
    local_path = uploads_dir / f"{file_id}{ext}"
    local_path.write_bytes(file_bytes)
    logger.info("Downloaded Feishu file to %s (%d bytes)", local_path, len(file_bytes))
    return str(local_path)


def _parse_message_event(
    event_data: dict[str, Any],
    *,
    app_id: str = "",
) -> UnifiedMessage | None:
    """Convert a Feishu message event into a UnifiedMessage."""
    message = event_data.get("message", {})
    sender = event_data.get("sender", {}).get("sender_id", {})

    msg_type_raw = message.get("message_type", "text")
    content_str = message.get("content", "{}")

    try:
        content_json = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        content_json = {"text": content_str}

    msg_type = MessageType.TEXT
    text_content = ""
    file_url = ""

    file_name_from_feishu = ""
    if msg_type_raw == "text":
        text_content = content_json.get("text", "")
    elif msg_type_raw == "image":
        msg_type = MessageType.IMAGE
        file_url = content_json.get("image_key", "")
    elif msg_type_raw == "file":
        msg_type = MessageType.FILE
        file_url = content_json.get("file_key", "")
        file_name_from_feishu = content_json.get("file_name", "")
    elif msg_type_raw == "interactive":
        msg_type = MessageType.CARD
        text_content = json.dumps(content_json, ensure_ascii=False)
    else:
        text_content = content_json.get("text", str(content_json))

    open_id = sender.get("open_id", "")
    union_id = sender.get("union_id", "")
    user_id = sender.get("user_id", "")
    chat_id = message.get("chat_id", "")
    chat_type = message.get("chat_type", "")

    return UnifiedMessage(
        channel=Channel.FEISHU,
        sender_id=open_id,
        content=text_content,
        msg_type=msg_type,
        file_url=file_url,
        file_name=file_name_from_feishu,
        raw={
            "message_id": message.get("message_id", ""),
            "chat_id": chat_id,
            "chat_type": chat_type,
            "open_id": open_id,
            "union_id": union_id,
            "user_id": user_id,
            "app_id": app_id,
            "event_data": event_data,
            "file_type": msg_type_raw,
        },
    )


async def _route_message(msg: UnifiedMessage) -> str | None:
    """Identify team from bot and hand off to the router; return assistant text."""
    from app.channels.router import route_inbound_message
    return await route_inbound_message(msg)


async def _send_feishu_reply(msg: UnifiedMessage, response_text: str) -> None:
    """Send assistant reply to the same Feishu chat (group or P2P)."""
    chat_id = (msg.raw or {}).get("chat_id", "")
    team_id = msg.team_id
    if not response_text.strip() or not chat_id or not team_id:
        return

    from app.skills.builtin import feishu_im as fim

    result = await fim._send_feishu_message(
        team_id,
        chat_id,
        response_text,
        receive_id_type="chat_id",
    )
    if result.get("sent"):
        return

    cfg = get_config()
    if cfg.feishu_app_id and cfg.feishu_app_secret:
        try:
            token = await fim._get_tenant_access_token(cfg.feishu_app_id, cfg.feishu_app_secret)
            inner = json.dumps({"text": response_text}, ensure_ascii=False)
            r2 = await fim.send_im_message_with_token(
                tenant_access_token=token,
                receive_id=chat_id,
                receive_id_type="chat_id",
                msg_type="text",
                content=inner,
            )
            if not r2.get("sent"):
                logger.warning("Feishu reply (fallback creds) failed: %s", r2.get("error"))
        except Exception as exc:
            logger.warning("Feishu reply (fallback creds) error: %s", exc)
    else:
        logger.warning("Feishu reply failed (no team bot creds): %s", result.get("error"))


def _parse_card_action_value(raw_val: Any) -> dict[str, Any]:
    if isinstance(raw_val, dict):
        return raw_val
    if raw_val in (None, ""):
        return {}
    if isinstance(raw_val, str):
        try:
            return json.loads(raw_val)
        except json.JSONDecodeError:
            return {}
    return {}


def _operator_open_id(event_data: dict[str, Any]) -> str:
    op = event_data.get("operator") or {}
    if op.get("open_id"):
        return str(op["open_id"])
    nested = op.get("operator_id")
    if isinstance(nested, dict) and nested.get("open_id"):
        return str(nested["open_id"])
    return ""


async def _handle_card_action(header: dict[str, Any], event_data: dict[str, Any]) -> None:
    """Process interactive card button clicks (approve / reject)."""
    action = event_data.get("action") or {}
    val = _parse_card_action_value(action.get("value"))
    act = val.get("action", "")
    approval_id = val.get("id", "")
    if act not in ("approve", "reject") or not approval_id:
        logger.info("Ignoring card action: act=%s id=%s", act, approval_id)
        return

    open_id = _operator_open_id(event_data)
    app_id = header.get("app_id", "")

    from app.channels.bot_manager import BotManager
    from app.core.database import Database
    from app.core.employee_manager import EmployeeManager
    from app.core.exceptions import ValidationError
    from app.safety.approval import ApprovalGateway
    from app.skills.builtin import feishu_im as fim

    manager = BotManager.get_instance()
    team_id = ""
    if app_id:
        team_id = manager.route_feishu_app_id_to_team(app_id) or ""
    if not team_id:
        db = Database.get_instance()
        rec = db.get_by_id("approval_requests", approval_id)
        if rec:
            team_id = rec.get("team_id", "") or ""

    em = EmployeeManager()
    emp = em.identify_by_sender("feishu", open_id) if open_id else None
    approver_id = emp.get("id", "") if emp else open_id or "unknown"

    gateway = ApprovalGateway.get_instance()
    approval_row: dict[str, Any] | None = None
    err_msg = ""
    try:
        if act == "approve":
            approval_row = await gateway.approve(approval_id, approver_id)
        else:
            approval_row = await gateway.reject(
                approval_id, approver_id, reason="飞书卡片驳回",
            )
    except ValidationError as exc:
        err_msg = str(exc)
        logger.warning("Card approval action failed: %s", exc)
    except Exception as exc:
        err_msg = str(exc)
        logger.exception("Card approval unexpected error")

    context = event_data.get("context") or {}
    message_id = (
        context.get("open_message_id")
        or context.get("message_id")
        or event_data.get("open_message_id")
        or ""
    )

    if not message_id or not team_id:
        return

    try:
        creds = manager.get_credentials(team_id, "feishu")
        token = await fim._get_tenant_access_token(
            creds.get("app_id", ""), creds.get("app_secret", ""),
        )
    except Exception as exc:
        logger.warning("Cannot get Feishu token to update card: %s", exc)
        return

    ar = approval_row or Database.get_instance().get_by_id("approval_requests", approval_id)
    title = (ar or {}).get("title", approval_id)
    if err_msg:
        card = fim.build_approval_result_card(
            approved=False,
            title=title,
            detail=f"操作未生效：{err_msg}",
        )
    elif act == "approve":
        card = fim.build_approval_result_card(
            approved=True,
            title=title,
            detail="该审批已通过。",
        )
    else:
        card = fim.build_approval_result_card(
            approved=False,
            title=title,
            detail="该审批已驳回。",
        )

    content_str = json.dumps(card, ensure_ascii=False)
    await fim.patch_interactive_message(
        tenant_access_token=token,
        message_id=message_id,
        content_card_json=content_str,
        message_id_type="open_message_id",
    )
