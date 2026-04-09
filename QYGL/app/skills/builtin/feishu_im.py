"""F13 Feishu IM Skill — send messages, cards, and upload files via Feishu Bot API.

Tools:
    feishu_im__send_message — send text/rich message
    feishu_im__send_card    — send interactive card
    feishu_im__upload_file  — upload a file to Feishu

Uses httpx.AsyncClient for token and HTTP calls; a synchronous token helper is
kept for backward compatibility in non-async contexts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.core.enums import PermissionLevel
from app.core.exceptions import ChannelConnectionFailed
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


def _get_bot_credentials(team_id: str) -> dict[str, str]:
    """Retrieve decrypted Feishu bot credentials for the team."""
    from app.channels.bot_manager import BotManager
    manager = BotManager.get_instance()
    creds = manager.get_credentials(team_id, "feishu")
    return creds


def _get_tenant_access_token_sync(app_id: str, app_secret: str) -> str:
    """Obtain a tenant_access_token (synchronous). Prefer ``_get_tenant_access_token`` in async code."""
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
    token = data.get("tenant_access_token", "")
    if not token:
        raise ChannelConnectionFailed("feishu", f"Failed to get token: {data}")
    return token


async def _get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Obtain a tenant_access_token from Feishu (async)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
    token = data.get("tenant_access_token", "")
    if not token:
        raise ChannelConnectionFailed("feishu", f"Failed to get token: {data}")
    return token


def build_approval_card(approval: dict) -> dict:
    """Build Feishu interactive card for an approval request."""
    aid = approval.get("id", "")
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"🔔 审批请求: {approval.get('title', '')}",
            },
            "template": "orange" if approval.get("priority", 2) <= 1 else "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**AI建议:** {approval.get('suggestion', '')}",
                },
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**推理依据:** {approval.get('reasoning', '')}",
                },
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**可信度:** {approval.get('confidence', 'B')} | "
                        f"**自动化级别:** {approval.get('automation_level', 'L2')}"
                    ),
                },
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 批准"},
                        "type": "primary",
                        "value": json.dumps({"action": "approve", "id": aid}, ensure_ascii=False),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 驳回"},
                        "type": "danger",
                        "value": json.dumps({"action": "reject", "id": aid}, ensure_ascii=False),
                    },
                ],
            },
        ],
    }


def build_approval_result_card(*, approved: bool, title: str, detail: str = "") -> dict:
    """Card body shown after an approval action is processed."""
    status = "✅ 已批准" if approved else "❌ 已驳回"
    template = "green" if approved else "red"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{status}: {title}"},
            "template": template,
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": detail or status},
            },
        ],
    }


async def send_im_message_with_token(
    *,
    tenant_access_token: str,
    receive_id: str,
    receive_id_type: str = "open_id",
    msg_type: str = "text",
    content: str,
) -> dict[str, Any]:
    """Send an IM message using an already-resolved tenant token (async)."""
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": content,
    }
    url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type={receive_id_type}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()
            if resp.status_code >= 400 or data.get("code", 0) != 0:
                return {
                    "sent": False,
                    "error": data.get("msg", f"HTTP {resp.status_code}"),
                }
            return {"sent": True, "message_id": data.get("data", {}).get("message_id", "")}
    except httpx.HTTPError as exc:
        logger.error("Feishu send (token) failed: %s", exc)
        return {"sent": False, "error": str(exc)}


async def patch_interactive_message(
    *,
    tenant_access_token: str,
    message_id: str,
    content_card_json: str,
    message_id_type: str = "open_message_id",
) -> dict[str, Any]:
    """PATCH an existing interactive (card) message."""
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}"
    params = {"message_id_type": message_id_type}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                url,
                params=params,
                json={"content": content_card_json},
                headers=headers,
            )
            data = resp.json()
            if resp.status_code >= 400 or data.get("code", 0) != 0:
                return {"ok": False, "error": data.get("msg", f"HTTP {resp.status_code}")}
            return {"ok": True, "data": data.get("data", {})}
    except httpx.HTTPError as exc:
        logger.error("Feishu patch message failed: %s", exc)
        return {"ok": False, "error": str(exc)}


async def _send_feishu_message(
    team_id: str,
    recipient_id: str,
    content: str,
    msg_type: str = "text",
    card_json: dict[str, Any] | None = None,
    *,
    receive_id_type: str = "open_id",
) -> dict[str, Any]:
    """Internal helper for sending a Feishu message."""
    try:
        creds = _get_bot_credentials(team_id)
    except Exception as exc:
        logger.warning("Cannot get Feishu credentials for team %s: %s", team_id, exc)
        return {"sent": False, "error": str(exc)}

    app_id = creds.get("app_id", "")
    app_secret = creds.get("app_secret", "")
    if not app_id or not app_secret:
        return {"sent": False, "error": "Missing Feishu app_id or app_secret"}

    try:
        token = await _get_tenant_access_token(app_id, app_secret)
    except Exception as exc:
        return {"sent": False, "error": f"Token error: {exc}"}

    if msg_type == "card" and card_json:
        content_str = json.dumps(card_json, ensure_ascii=False)
        payload_content = content_str
        api_msg_type = "interactive"
    else:
        payload_content = json.dumps({"text": content}, ensure_ascii=False)
        api_msg_type = "text"

    return await send_im_message_with_token(
        tenant_access_token=token,
        receive_id=recipient_id,
        receive_id_type=receive_id_type,
        msg_type=api_msg_type,
        content=payload_content,
    )


@tool(permission=PermissionLevel.P1, description="Send a text or rich message via Feishu")
async def feishu_im__send_message(
    ctx: ToolContext,
    *,
    recipient_id: str,
    content: str,
    msg_type: str = "text",
) -> dict[str, Any]:
    """Send a message to a Feishu user by open_id."""
    return await _send_feishu_message(ctx.team_id, recipient_id, content, msg_type)


@tool(permission=PermissionLevel.P1, description="Send an interactive card via Feishu")
async def feishu_im__send_card(
    ctx: ToolContext,
    *,
    recipient_id: str,
    card_json: dict[str, Any],
) -> dict[str, Any]:
    """Send an interactive card message to a Feishu user."""
    return await _send_feishu_message(ctx.team_id, recipient_id, "", "card", card_json)


@tool(permission=PermissionLevel.P1, description="Upload a file to Feishu")
async def feishu_im__upload_file(
    ctx: ToolContext,
    *,
    file_path: str,
    file_type: str = "stream",
    file_name: str = "",
) -> dict[str, Any]:
    """Upload a local file to Feishu and return the file_key."""
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        creds = _get_bot_credentials(ctx.team_id)
    except Exception as exc:
        return {"error": str(exc)}

    app_id = creds.get("app_id", "")
    app_secret = creds.get("app_secret", "")
    if not app_id or not app_secret:
        return {"error": "Missing Feishu credentials"}

    try:
        token = await _get_tenant_access_token(app_id, app_secret)
    except Exception as exc:
        return {"error": f"Token error: {exc}"}

    headers = {"Authorization": f"Bearer {token}"}
    name = file_name or p.name

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{FEISHU_API_BASE}/im/v1/files",
                headers=headers,
                data={"file_type": file_type, "file_name": name},
                files={"file": (name, p.read_bytes())},
            )
            resp.raise_for_status()
            data = resp.json()
            return {"file_key": data.get("data", {}).get("file_key", ""), "file_name": name}
    except httpx.HTTPError as exc:
        return {"error": str(exc)}
