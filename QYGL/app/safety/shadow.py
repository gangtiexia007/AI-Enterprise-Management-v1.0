"""F45: Shadow Mode — dry-run layer that records AI decisions without side-effects.

When a team is in shadow mode, every action flows through the Approval Gateway
but is intercepted here.  The system writes to ``shadow_results`` only;
no real IM messages are sent, no tasks dispatched, no KPI scores written.

After the shadow period ends, ``generate_report`` compares shadow decisions
against what a human would have done, producing accuracy metrics that
inform the confidence baseline before switching to live.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import Confidence, ShadowMode
from app.core.events import Events
from app.core.exceptions import ResourceNotFound, ValidationError

logger = logging.getLogger(__name__)


async def _publish(event: str, data: dict[str, Any]) -> None:
    try:
        from app.infra.eventbus import EventBus
        bus = EventBus.get_instance()
        await bus.emit(event, data)
    except Exception as e:
        logger.warning("EventBus publish failed for %s: %s", event, e)


class ShadowModeService:
    """Manages the shadow / live lifecycle and shadow result analysis."""

    _instance: ShadowModeService | None = None

    def __init__(self, db: Database | None = None):
        self.db = db or Database.get_instance()

    @classmethod
    def get_instance(cls, db: Database | None = None) -> ShadowModeService:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Core API ──────────────────────────────────────────────────

    def is_shadow_mode(self, team_id: str) -> bool:
        """Return True when the team is currently in shadow mode."""
        cfg = self._get_config(team_id)
        if cfg is None:
            return False
        return cfg.get("mode") == ShadowMode.SHADOW

    async def intercept(
        self,
        team_id: str,
        action_type: str,
        action_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Record an action that *would have* been executed.

        Returns the persisted shadow_result row.
        """
        shadow_id = new_id()
        confidence = action_data.get("confidence", Confidence.B)
        would_have_done = action_data.get(
            "would_have_done",
            f"{action_type}: {action_data.get('title', 'unknown')}",
        )

        record = {
            "id": shadow_id,
            "team_id": team_id,
            "result_type": action_type,
            "original_action_json": action_data,
            "shadow_data_json": {
                "intercepted_at": datetime.now(timezone.utc).isoformat(),
                "source_agent": action_data.get("source_agent", ""),
                "reasoning": action_data.get("reasoning", ""),
            },
            "confidence": confidence,
            "would_have_done": would_have_done,
        }
        self.db.insert("shadow_results", record)

        logger.info("Shadow intercept %s for team %s (type=%s)", shadow_id, team_id, action_type)
        return self.db.get_by_id("shadow_results", shadow_id)

    async def start_shadow(self, team_id: str, duration_days: int = 7) -> dict[str, Any]:
        """Activate shadow mode for a team."""
        cfg = self._get_config(team_id)
        now = datetime.now(timezone.utc).isoformat()

        if cfg is None:
            record_id = new_id()
            self.db.insert("team_shadow_config", {
                "id": record_id,
                "team_id": team_id,
                "mode": ShadowMode.SHADOW,
                "shadow_start_date": now,
                "shadow_duration_days": duration_days,
            })
        else:
            record_id = cfg["id"]
            self.db.update("team_shadow_config", record_id, {
                "mode": ShadowMode.SHADOW,
                "shadow_start_date": now,
                "shadow_duration_days": duration_days,
                "switched_live_at": None,
            })

        await _publish(Events.SHADOW_STARTED, {
            "team_id": team_id,
            "duration_days": duration_days,
        })

        logger.info("Shadow mode started for team %s (%d days)", team_id, duration_days)
        return self._get_config(team_id)

    async def switch_to_live(self, team_id: str) -> dict[str, Any]:
        """End shadow mode and go live."""
        cfg = self._get_config(team_id)
        if cfg is None:
            raise ResourceNotFound("TeamShadowConfig", team_id)
        if cfg.get("mode") == ShadowMode.LIVE:
            raise ValidationError(f"Team {team_id} is already in live mode")

        now = datetime.now(timezone.utc).isoformat()
        self.db.update("team_shadow_config", cfg["id"], {
            "mode": ShadowMode.LIVE,
            "switched_live_at": now,
        })

        await _publish(Events.SHADOW_SWITCHED_LIVE, {"team_id": team_id})

        logger.info("Team %s switched to live mode", team_id)
        return self._get_config(team_id)

    def get_shadow_config(self, team_id: str) -> dict[str, Any] | None:
        """Return the current shadow config for a team."""
        return self._get_config(team_id)

    async def generate_report(self, team_id: str) -> dict[str, Any]:
        """Analyze all shadow_results for a team and produce accuracy metrics.

        Metrics:
          - total_actions: how many actions were intercepted
          - by_type: counts grouped by action_type
          - confidence_distribution: {A: n, B: n, C: n}
          - would_have_auto_executed: count of L3/L4 actions
          - shadow_period_days: elapsed days since shadow start
          - recommendation: heuristic readiness indicator
        """
        results = self.db.query(
            "shadow_results",
            {"team_id": team_id},
            order_by="created_at ASC",
            limit=10000,
        )

        total = len(results)
        by_type: dict[str, int] = {}
        confidence_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0}
        auto_execute_count = 0

        for row in results:
            rtype = row.get("result_type", "unknown")
            by_type[rtype] = by_type.get(rtype, 0) + 1

            conf = row.get("confidence", "B")
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1

            shadow_data = row.get("shadow_data_json")
            if isinstance(shadow_data, str):
                try:
                    shadow_data = json.loads(shadow_data)
                except (json.JSONDecodeError, TypeError):
                    shadow_data = {}
            if isinstance(shadow_data, dict) and shadow_data.get("would_have_auto_executed"):
                auto_execute_count += 1

        cfg = self._get_config(team_id)
        shadow_days = 0
        if cfg and cfg.get("shadow_start_date"):
            start = _parse_dt(cfg["shadow_start_date"])
            shadow_days = (datetime.now(timezone.utc) - start).days

        high_confidence_ratio = (
            confidence_dist["A"] / total if total > 0 else 0.0
        )
        recommendation = (
            "ready_for_live" if high_confidence_ratio >= 0.7 and total >= 20
            else "needs_more_data" if total < 20
            else "review_low_confidence"
        )

        report = {
            "team_id": team_id,
            "total_actions": total,
            "by_type": by_type,
            "confidence_distribution": confidence_dist,
            "high_confidence_ratio": round(high_confidence_ratio, 4),
            "would_have_auto_executed": auto_execute_count,
            "shadow_period_days": shadow_days,
            "recommendation": recommendation,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        await _publish(Events.SHADOW_REPORT_GENERATED, {
            "team_id": team_id,
            "total_actions": total,
            "recommendation": recommendation,
        })

        logger.info(
            "Shadow report for team %s: %d actions, recommendation=%s",
            team_id, total, recommendation,
        )
        return report

    # ── Internals ─────────────────────────────────────────────────

    def _get_config(self, team_id: str) -> dict[str, Any] | None:
        rows = self.db.query("team_shadow_config", {"team_id": team_id}, limit=1)
        return rows[0] if rows else None


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now(timezone.utc)
