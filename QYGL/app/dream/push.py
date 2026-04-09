"""Push dream reports to IM channels (Feishu / WeCom)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.database import Database

logger = logging.getLogger(__name__)


def _parse_extra(bot: dict[str, Any]) -> dict[str, Any]:
    raw = bot.get("extra_json", "{}")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


async def push_report_to_im(report_id: str) -> dict[str, Any]:
    """Push a dream report to the team's configured IM channel(s)."""
    db = Database.get_instance()
    report = db.get_by_id("dream_reports", report_id)
    if not report:
        return {"ok": False, "error": "report not found"}

    team_id = report.get("team_id", "")
    if not team_id:
        return {"ok": False, "error": "no team_id"}

    summary = report.get("summary", "暂无摘要")
    title = f"📊 {report.get('report_type', 'daily')}报告 - {report.get('date', '')}"
    body = f"{title}\n\n{summary}"

    bots = db.query("team_bots", {"team_id": team_id, "enabled": True}, limit=20)
    if not bots:
        logger.info(
            "No enabled team_bots for team %s; report %s not pushed",
            team_id,
            report_id,
        )
        return {"ok": True, "pushed": [], "note": "no_bots"}

    results: list[dict[str, Any]] = []
    for bot in bots:
        channel = bot.get("channel", "")
        webhook = (bot.get("webhook_url") or "").strip()
        extra = _parse_extra(bot)

        if channel == "wecom" and webhook:
            results.append(
                {"channel": "wecom", **await _post_wecom_webhook(webhook, body)},
            )
        elif channel == "feishu":
            if webhook:
                results.append(
                    {
                        "channel": "feishu_webhook",
                        **await _post_feishu_webhook(webhook, body),
                    },
                )
            else:
                open_id = extra.get("notify_open_id") or extra.get("open_id")
                if open_id:
                    from app.skills.builtin.feishu_im import _send_feishu_message

                    send_result = await _send_feishu_message(
                        team_id, open_id, body, "text",
                    )
                    results.append({"channel": "feishu_im", **send_result})
                else:
                    logger.info(
                        "Feishu push skipped (team=%s): set webhook_url or "
                        "extra_json.notify_open_id",
                        team_id,
                    )
                    results.append(
                        {
                            "channel": "feishu",
                            "sent": False,
                            "skipped": True,
                            "reason": "no_webhook_or_open_id",
                        },
                    )

    return {"ok": True, "pushed": results}


async def _post_wecom_webhook(webhook_url: str, text: str) -> dict[str, Any]:
    payload = {"msgtype": "text", "text": {"content": text}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        if data.get("errcode", 0) != 0:
            return {"sent": False, "error": data.get("errmsg", "wecom error")}
        return {"sent": True}
    except Exception as exc:
        logger.warning("WeCom webhook push failed: %s", exc)
        return {"sent": False, "error": str(exc)}


async def _post_feishu_webhook(webhook_url: str, text: str) -> dict[str, Any]:
    payload = {"msg_type": "text", "content": {"text": text}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                data = {}
        if isinstance(data, dict) and data.get("code") not in (0, None):
            return {"sent": False, "error": str(data)}
        return {"sent": True}
    except Exception as exc:
        logger.warning("Feishu webhook push failed: %s", exc)
        return {"sent": False, "error": str(exc)}


def push_report_sync(report_id: str) -> dict[str, Any]:
    """Run :func:`push_report_to_im` from synchronous code (e.g. APScheduler)."""
    try:
        return asyncio.run(push_report_to_im(report_id))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(push_report_to_im(report_id))
        finally:
            loop.close()
