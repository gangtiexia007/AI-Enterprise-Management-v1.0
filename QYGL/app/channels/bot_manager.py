"""F25: Bot Manager — encrypted credential storage, hot-reload, bot↔team routing.

Responsibilities:
* Store bot credentials in ``team_bots`` table (app_id / app_secret encrypted
  with Fernet via ``app.core.security``).
* Maintain an in-memory ``bot_id → team_id`` routing table.
* Hot-reload: credential changes take effect without restarting the server.
* Test-connection endpoint helper.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import Channel
from app.core.exceptions import BotCredentialInvalid, ChannelConnectionFailed
from app.core import security

logger = logging.getLogger(__name__)


class BotManager:
    """Manage bot credentials and the bot→team routing table."""

    _instance: BotManager | None = None

    def __init__(self, db: Database | None = None):
        self._db = db or Database.get_instance()
        self._route_table: dict[str, str] = {}
        self._credentials_cache: dict[str, dict[str, str]] = {}

    @classmethod
    def get_instance(cls, db: Database | None = None) -> BotManager:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Credential CRUD ───────────────────────────────────────────

    def register_bot(
        self,
        *,
        team_id: str,
        channel: str,
        app_id: str = "",
        app_secret: str = "",
        webhook_url: str = "",
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Register (or update) a bot for a team + channel pair."""
        existing = self._db.query(
            "team_bots", {"team_id": team_id, "channel": channel}, limit=1,
        )

        encrypted_id = security.encrypt(app_id) if app_id else ""
        encrypted_secret = security.encrypt(app_secret) if app_secret else ""

        if existing:
            bot_id = existing[0]["id"]
            self._db.update("team_bots", bot_id, {
                "app_id_encrypted": encrypted_id,
                "app_secret_encrypted": encrypted_secret,
                "webhook_url": webhook_url,
                "extra_json": json.dumps(extra or {}, ensure_ascii=False),
                "enabled": True,
            })
        else:
            bot_id = new_id()
            self._db.insert("team_bots", {
                "id": bot_id,
                "team_id": team_id,
                "channel": channel,
                "app_id_encrypted": encrypted_id,
                "app_secret_encrypted": encrypted_secret,
                "webhook_url": webhook_url,
                "extra_json": json.dumps(extra or {}, ensure_ascii=False),
                "enabled": True,
                "verified": False,
            })

        self._invalidate_cache(team_id, channel)
        self._rebuild_route_table()
        logger.info("Bot registered: team=%s channel=%s bot_id=%s", team_id, channel, bot_id)
        return bot_id

    def get_credentials(self, team_id: str, channel: str) -> dict[str, str]:
        """Return decrypted credentials for a team/channel."""
        cache_key = f"{team_id}:{channel}"
        if cache_key in self._credentials_cache:
            return self._credentials_cache[cache_key]

        rows = self._db.query(
            "team_bots", {"team_id": team_id, "channel": channel, "enabled": True}, limit=1,
        )
        if not rows:
            raise BotCredentialInvalid(channel, team_id)

        row = rows[0]
        creds = {
            "bot_id": row["id"],
            "app_id": security.decrypt(row.get("app_id_encrypted", "")),
            "app_secret": security.decrypt(row.get("app_secret_encrypted", "")),
            "webhook_url": row.get("webhook_url", ""),
        }
        extra = row.get("extra_json", "{}")
        if isinstance(extra, str):
            try:
                creds["extra"] = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                creds["extra"] = {}
        else:
            creds["extra"] = extra

        self._credentials_cache[cache_key] = creds
        return creds

    def disable_bot(self, bot_id: str) -> None:
        self._db.update("team_bots", bot_id, {"enabled": False})
        self._rebuild_route_table()
        self._credentials_cache.clear()
        logger.info("Bot disabled: %s", bot_id)

    def mark_verified(self, bot_id: str) -> None:
        self._db.update("team_bots", bot_id, {"verified": True})

    # ── Routing ───────────────────────────────────────────────────

    def route_bot_to_team(self, bot_id: str) -> str | None:
        """Look up team_id for a bot_id (used by inbound message routing)."""
        if not self._route_table:
            self._rebuild_route_table()
        return self._route_table.get(bot_id)

    def route_app_id_to_team(self, app_id_encrypted: str) -> str | None:
        """Look up team by encrypted app_id (feishu webhook may send app_id)."""
        rows = self._db.query(
            "team_bots", {"app_id_encrypted": app_id_encrypted, "enabled": True}, limit=1,
        )
        return rows[0]["team_id"] if rows else None

    def route_feishu_app_id_to_team(self, plain_app_id: str) -> str | None:
        """Map Feishu bot App ID (plaintext) to team_id via stored team_bots credentials."""
        if not plain_app_id:
            return None
        rows = self._db.query(
            "team_bots",
            {"channel": Channel.FEISHU, "enabled": True},
            limit=500,
        )
        for r in rows:
            try:
                decrypted = security.decrypt(r.get("app_id_encrypted", ""))
            except Exception:
                decrypted = ""
            if decrypted == plain_app_id:
                return r.get("team_id")
        return None

    def get_team_bots(self, team_id: str) -> list[dict[str, Any]]:
        rows = self._db.query("team_bots", {"team_id": team_id})
        safe: list[dict[str, Any]] = []
        for r in rows:
            entry = {k: v for k, v in r.items() if k not in ("app_id_encrypted", "app_secret_encrypted")}
            entry["has_credentials"] = bool(r.get("app_id_encrypted"))
            safe.append(entry)
        return safe

    # ── Hot Reload ────────────────────────────────────────────────

    def hot_reload(self) -> None:
        """Clear caches and rebuild the routing table from DB."""
        self._credentials_cache.clear()
        self._rebuild_route_table()
        logger.info("BotManager hot-reloaded")

    # ── Test Connection ───────────────────────────────────────────

    async def test_connection(self, team_id: str, channel: str) -> dict[str, Any]:
        """Verify credentials are valid by making a lightweight API call."""
        try:
            creds = self.get_credentials(team_id, channel)
        except BotCredentialInvalid:
            return {"ok": False, "error": "No credentials configured"}

        if channel == Channel.FEISHU:
            return await self._test_feishu(creds)
        elif channel == Channel.WECOM:
            return await self._test_wecom(creds)
        return {"ok": False, "error": f"Unsupported channel: {channel}"}

    # ── Internals ─────────────────────────────────────────────────

    def _rebuild_route_table(self) -> None:
        rows = self._db.query("team_bots", {"enabled": True}, limit=500)
        self._route_table = {r["id"]: r["team_id"] for r in rows}

    def _invalidate_cache(self, team_id: str, channel: str) -> None:
        cache_key = f"{team_id}:{channel}"
        self._credentials_cache.pop(cache_key, None)

    @staticmethod
    async def _test_feishu(creds: dict[str, str]) -> dict[str, Any]:
        import httpx
        app_id = creds.get("app_id", "")
        app_secret = creds.get("app_secret", "")
        if not app_id or not app_secret:
            return {"ok": False, "error": "Missing app_id or app_secret"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                    json={"app_id": app_id, "app_secret": app_secret},
                )
                data = resp.json()
                if data.get("tenant_access_token"):
                    return {"ok": True, "message": "Feishu credentials valid"}
                return {"ok": False, "error": data.get("msg", "Unknown error")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    async def _test_wecom(creds: dict[str, str]) -> dict[str, Any]:
        import httpx
        webhook_url = creds.get("webhook_url", "")
        if not webhook_url:
            return {"ok": False, "error": "No webhook URL configured"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    webhook_url,
                    json={"msgtype": "text", "text": {"content": "Connection test"}},
                )
                data = resp.json()
                if data.get("errcode", -1) == 0:
                    return {"ok": True, "message": "WeCom webhook valid"}
                return {"ok": False, "error": data.get("errmsg", "Unknown error")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
