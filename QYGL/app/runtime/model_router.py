"""F09: Model Router — model selection, token budget tracking, automatic fallback.

Each team has a ``primary_model`` and ``fallback_model``.  The router:

1. Selects the appropriate model based on team config.
2. Tracks per-model per-team per-day token usage in ``model_usage``.
3. Emits budget alerts at 80 / 90 / 95 % thresholds.
4. Falls back to the fallback model (or system default) when the budget is
   exceeded or the primary model is unavailable.

Uses ``Model`` and ``ModelUsage`` from ``app.core.models``.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import TeamStatus
from app.core.events import Events
from app.core.exceptions import BudgetExceeded, ModelNotFound

logger = logging.getLogger(__name__)

BUDGET_THRESHOLDS = (0.80, 0.90, 0.95)
SYSTEM_DEFAULT_MODEL = "gpt-4o-mini"


class ModelRouter:
    """Select the best available model for a team, respecting token budgets."""

    _instance: ModelRouter | None = None

    def __init__(self, db: Database | None = None):
        self._db = db or Database.get_instance()
        self._alerted: dict[str, set[float]] = {}

    @classmethod
    def get_instance(cls, db: Database | None = None) -> ModelRouter:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Model Selection ──────────────────────────────────────────

    def select_model(self, team_id: str) -> str:
        """Pick the best model for *team_id* considering budget and availability.

        Returns the litellm model string (e.g. ``gpt-4o``).
        """
        team = self._get_team(team_id)
        primary = team.get("primary_model", "")
        fallback = team.get("fallback_model", "")

        if primary and self._is_available(primary, team_id):
            return primary

        if primary:
            self._emit_fallback(team_id, primary, fallback or SYSTEM_DEFAULT_MODEL)

        if fallback and self._is_available(fallback, team_id):
            return fallback

        return SYSTEM_DEFAULT_MODEL

    def select_model_for_sub_agent(
        self, team_id: str, model_override: str = "",
    ) -> str:
        """Sub-agents can override the model; falls back to team primary."""
        if model_override:
            if self._is_available(model_override, team_id):
                return model_override
        return self.select_model(team_id)

    def select_cheap_model(self) -> str:
        """Select cheapest enabled model for compression tasks."""
        rows = self._db.query("models", {"enabled": 1}, order_by="cost_tier ASC", limit=1)
        if rows:
            return rows[0]["name"]
        return "deepseek-chat"

    def decrypt_api_key_for_model(self, model_name: str) -> str | None:
        """Return decrypted API key for a model row, if present."""
        row = self._get_model_row(model_name)
        if not row:
            return None
        enc = row.get("api_key_encrypted") or ""
        if not enc:
            return None
        try:
            from app.core.security import decrypt

            return decrypt(enc)
        except Exception:
            logger.warning("Failed to decrypt API key for model %s", model_name, exc_info=True)
            return None

    def get_model_with_key(self, team_id: str) -> dict[str, Any]:
        """Return selected model name plus optional decrypted api_key for *team_id*."""
        model_name = self.select_model(team_id)
        row = self._get_model_row(model_name)
        out: dict[str, Any] = {"model": model_name}
        if row:
            out["model_id"] = row.get("id", "")
            key = self.decrypt_api_key_for_model(model_name)
            out["api_key"] = key
        else:
            out["model_id"] = ""
            out["api_key"] = None
        return out

    # ── Token Tracking ───────────────────────────────────────────

    def record_usage(
        self,
        model_name: str,
        team_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record token usage for today.  Upserts the ``model_usage`` row."""
        today = date.today().isoformat()
        model_id = self._resolve_model_id(model_name)
        total = prompt_tokens + completion_tokens

        existing = self._db.query("model_usage", {
            "model_id": model_id,
            "team_id": team_id,
            "date": today,
        }, limit=1)

        if existing:
            row = existing[0]
            self._db.update("model_usage", row["id"], {
                "prompt_tokens": row["prompt_tokens"] + prompt_tokens,
                "completion_tokens": row["completion_tokens"] + completion_tokens,
                "total_tokens": row["total_tokens"] + total,
            })
        else:
            self._db.insert("model_usage", {
                "id": new_id(),
                "model_id": model_id,
                "team_id": team_id,
                "date": today,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total,
            })

        self._check_budget_alerts(model_id, model_name, team_id)

    def get_daily_usage(self, model_name: str, team_id: str) -> int:
        """Return total tokens used today for *model_name* × *team_id*."""
        model_id = self._resolve_model_id(model_name)
        today = date.today().isoformat()
        rows = self._db.query("model_usage", {
            "model_id": model_id,
            "team_id": team_id,
            "date": today,
        }, limit=1)
        return rows[0]["total_tokens"] if rows else 0

    def get_team_usage_summary(self, team_id: str) -> list[dict[str, Any]]:
        """Return all model usage rows for *team_id* today."""
        today = date.today().isoformat()
        return self._db.query("model_usage", {
            "team_id": team_id,
            "date": today,
        })

    # ── Availability ─────────────────────────────────────────────

    def _is_available(self, model_name: str, team_id: str) -> bool:
        """A model is available when it is enabled and within its daily budget."""
        model_row = self._get_model_row(model_name)
        if not model_row:
            return True  # unknown model → assume external, no local budget

        if not model_row.get("enabled", True):
            return False

        daily_limit = model_row.get("daily_token_limit", 0)
        if daily_limit <= 0:
            return True

        used = self.get_daily_usage(model_name, team_id)
        return used < daily_limit

    # ── Budget Alerts ────────────────────────────────────────────

    def _check_budget_alerts(
        self, model_id: str, model_name: str, team_id: str,
    ) -> None:
        model_row = self._get_model_row_by_id(model_id)
        if not model_row:
            return
        daily_limit = model_row.get("daily_token_limit", 0)
        if daily_limit <= 0:
            return

        used = self.get_daily_usage(model_name, team_id)
        ratio = used / daily_limit
        alert_key = f"{model_id}:{team_id}:{date.today().isoformat()}"

        for threshold in BUDGET_THRESHOLDS:
            if ratio >= threshold and threshold not in self._alerted.get(alert_key, set()):
                self._alerted.setdefault(alert_key, set()).add(threshold)
                pct = int(threshold * 100)
                logger.warning(
                    "Model budget %d%% alert: %s (team=%s) — %d/%d tokens",
                    pct, model_name, team_id, used, daily_limit,
                )
                self._emit_budget_warning(team_id, model_name, pct, used, daily_limit)

        if ratio >= 1.0:
            self._emit_budget_exceeded(team_id, model_name, used, daily_limit)

    # ── Event Emitters ───────────────────────────────────────────

    @staticmethod
    def _emit_budget_warning(
        team_id: str, model_name: str, pct: int, used: int, limit: int,
    ) -> None:
        try:
            from app.infra.eventbus import EventBus
            bus = EventBus.get_instance()
            bus.emit_nowait(Events.MODEL_BUDGET_WARNING, {
                "team_id": team_id,
                "model": model_name,
                "threshold_pct": pct,
                "used_tokens": used,
                "daily_limit": limit,
            })
        except Exception:
            logger.debug("Failed to emit budget warning event", exc_info=True)

    @staticmethod
    def _emit_budget_exceeded(
        team_id: str, model_name: str, used: int, limit: int,
    ) -> None:
        try:
            from app.infra.eventbus import EventBus
            bus = EventBus.get_instance()
            bus.emit_nowait(Events.MODEL_BUDGET_EXCEEDED, {
                "team_id": team_id,
                "model": model_name,
                "used_tokens": used,
                "daily_limit": limit,
            })
        except Exception:
            logger.debug("Failed to emit budget exceeded event", exc_info=True)

    @staticmethod
    def _emit_fallback(team_id: str, primary: str, fallback: str) -> None:
        try:
            from app.infra.eventbus import EventBus
            bus = EventBus.get_instance()
            bus.emit_nowait(Events.MODEL_FALLBACK_TRIGGERED, {
                "team_id": team_id,
                "primary_model": primary,
                "fallback_model": fallback,
            })
        except Exception:
            logger.debug("Failed to emit fallback event", exc_info=True)

    # ── DB Helpers ───────────────────────────────────────────────

    def _get_team(self, team_id: str) -> dict[str, Any]:
        row = self._db.get_by_id("teams", team_id)
        return row or {}

    def _get_model_row(self, model_name: str) -> dict[str, Any] | None:
        rows = self._db.query("models", {"name": model_name}, limit=1)
        return rows[0] if rows else None

    def _get_model_row_by_id(self, model_id: str) -> dict[str, Any] | None:
        return self._db.get_by_id("models", model_id)

    def _resolve_model_id(self, model_name: str) -> str:
        """Return the database ID for *model_name*, creating a stub row if needed."""
        row = self._get_model_row(model_name)
        if row:
            return row["id"]
        mid = new_id()
        self._db.insert("models", {
            "id": mid,
            "name": model_name,
            "provider": model_name.split("/")[0] if "/" in model_name else "openai",
            "enabled": True,
        })
        return mid
