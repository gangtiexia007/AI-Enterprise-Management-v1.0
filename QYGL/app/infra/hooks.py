"""F30: Hook Engine — event → condition → action pipeline.

Hook rules are stored in the ``hook_rules`` table (auto-created) and can be
configured from the dashboard.  When an event fires, the engine evaluates the
``simpleeval`` condition expression against the event payload and executes the
mapped action.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import Database, new_id

logger = logging.getLogger(__name__)

_HOOK_TABLE_CREATED = False

ALLOWED_ACTIONS = {
    "send_notification",
    "create_approval",
    "create_task",
    "update_status",
    "log_warning",
    "emit_event",
}


def _ensure_hook_table(db: Database) -> None:
    """Create the ``hook_rules`` table if it doesn't exist yet."""
    global _HOOK_TABLE_CREATED
    if _HOOK_TABLE_CREATED:
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS hook_rules (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL DEFAULT '',
            event_name TEXT NOT NULL,
            condition_expr TEXT NOT NULL DEFAULT '1',
            action_type TEXT NOT NULL,
            action_config_json TEXT NOT NULL DEFAULT '{}',
            priority INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    _HOOK_TABLE_CREATED = True


class HookEngine:
    """Evaluate hook rules against incoming events."""

    _instance: HookEngine | None = None

    def __init__(self, db: Database | None = None):
        self._db = db or Database.get_instance()
        _ensure_hook_table(self._db)
        self._rules_cache: dict[str, list[dict[str, Any]]] = {}
        self._cache_ts: float = 0.0

    @classmethod
    def get_instance(cls, db: Database | None = None) -> HookEngine:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Rule CRUD ─────────────────────────────────────────────────

    def add_rule(
        self,
        *,
        team_id: str = "",
        event_name: str,
        condition_expr: str = "1",
        action_type: str,
        action_config: dict[str, Any] | None = None,
        priority: int = 0,
        description: str = "",
    ) -> str:
        if action_type not in ALLOWED_ACTIONS:
            raise ValueError(f"Unknown action_type: {action_type}. Allowed: {ALLOWED_ACTIONS}")
        rule_id = new_id()
        self._db.insert("hook_rules", {
            "id": rule_id,
            "team_id": team_id,
            "event_name": event_name,
            "condition_expr": condition_expr,
            "action_type": action_type,
            "action_config_json": json.dumps(action_config or {}, ensure_ascii=False),
            "priority": priority,
            "enabled": 1,
            "description": description,
        })
        self._invalidate_cache()
        return rule_id

    def update_rule(self, rule_id: str, **fields: Any) -> None:
        if "action_config" in fields:
            fields["action_config_json"] = json.dumps(fields.pop("action_config"), ensure_ascii=False)
        if "enabled" in fields:
            fields["enabled"] = int(fields["enabled"])
        self._db.update("hook_rules", rule_id, fields)
        self._invalidate_cache()

    def delete_rule(self, rule_id: str) -> None:
        self._db.delete("hook_rules", rule_id)
        self._invalidate_cache()

    def list_rules(self, team_id: str = "", event_name: str = "") -> list[dict[str, Any]]:
        conditions: dict[str, Any] = {}
        if team_id:
            conditions["team_id"] = team_id
        if event_name:
            conditions["event_name"] = event_name
        rows = self._db.query("hook_rules", conditions or None, order_by="priority DESC", limit=200)
        return [self._parse_row(r) for r in rows]

    # ── Evaluation ────────────────────────────────────────────────

    async def process_event(self, event_name: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate all matching rules and execute actions.

        Returns a list of action results.
        """
        rules = self._get_matching_rules(event_name, payload.get("team_id", ""))
        results: list[dict[str, Any]] = []

        for rule in rules:
            try:
                if not self._evaluate_condition(rule["condition_expr"], payload):
                    continue
                action_result = await self._execute_action(
                    rule["action_type"],
                    rule.get("action_config_json", {}),
                    payload,
                    rule,
                )
                results.append({
                    "rule_id": rule["id"],
                    "action_type": rule["action_type"],
                    "success": True,
                    "result": action_result,
                })
            except Exception as exc:
                logger.error("Hook rule %s failed: %s", rule["id"], exc, exc_info=True)
                results.append({
                    "rule_id": rule["id"],
                    "action_type": rule["action_type"],
                    "success": False,
                    "error": str(exc),
                })

        return results

    def register_with_eventbus(self) -> None:
        """Subscribe to all events via the EventBus."""
        from app.infra.eventbus import EventBus
        bus = EventBus.get_instance()
        bus.subscribe_all(self._on_event)
        logger.info("HookEngine registered with EventBus (wildcard)")

    async def _on_event(self, event_name: str, payload: dict[str, Any]) -> None:
        await self.process_event(event_name, payload)

    # ── Internal ──────────────────────────────────────────────────

    def _get_matching_rules(
        self,
        event_name: str,
        team_id: str,
    ) -> list[dict[str, Any]]:
        """Return enabled rules matching the event and team scope."""
        rows = self._db.execute(
            "SELECT * FROM hook_rules WHERE enabled = 1 AND event_name = ? "
            "AND (team_id = '' OR team_id = ?) ORDER BY priority DESC",
            (event_name, team_id),
        )
        return [self._parse_row(r) for r in rows]

    @staticmethod
    def _evaluate_condition(expr: str, payload: dict[str, Any]) -> bool:
        """Evaluate a simpleeval expression against the event payload."""
        if not expr or expr.strip() in ("1", "true", "True"):
            return True
        try:
            from simpleeval import simple_eval
            result = simple_eval(expr, names=payload)
            return bool(result)
        except ImportError:
            raise RuntimeError("simpleeval is required but not installed. Run: pip install simpleeval")
        except Exception as exc:
            logger.warning("Condition eval failed: %s — %s", expr, exc)
            return False

    @staticmethod
    async def _execute_action(
        action_type: str,
        action_config: dict[str, Any],
        payload: dict[str, Any],
        rule: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the configured action."""
        if action_type == "log_warning":
            msg = action_config.get("message", f"Hook triggered: {rule.get('description', rule['id'])}")
            logger.warning("[HOOK] %s — payload=%s", msg, {k: v for k, v in payload.items() if not k.startswith("_")})
            return {"logged": True}

        if action_type == "emit_event":
            from app.infra.eventbus import EventBus
            bus = EventBus.get_instance()
            new_event = action_config.get("event_name", "")
            if new_event:
                await bus.emit(new_event, {**payload, "_source_hook": rule["id"]})
                return {"emitted": new_event}
            return {"emitted": None}

        if action_type == "send_notification":
            from app.infra.audit import AuditWriter
            AuditWriter.get_instance().write(
                actor="hook_engine",
                team_id=payload.get("team_id", ""),
                action="hook:send_notification",
                resource_type="hook_rule",
                resource_id=rule["id"],
                details_json=action_config,
            )
            return {"queued": True, "config": action_config}

        if action_type == "create_approval":
            from app.infra.audit import AuditWriter
            AuditWriter.get_instance().write(
                actor="hook_engine",
                team_id=payload.get("team_id", ""),
                action="hook:create_approval",
                resource_type="hook_rule",
                resource_id=rule["id"],
                details_json=action_config,
            )
            return {"queued": True, "config": action_config}

        if action_type == "create_task":
            from app.infra.audit import AuditWriter
            AuditWriter.get_instance().write(
                actor="hook_engine",
                team_id=payload.get("team_id", ""),
                action="hook:create_task",
                resource_type="hook_rule",
                resource_id=rule["id"],
                details_json=action_config,
            )
            return {"queued": True, "config": action_config}

        if action_type == "update_status":
            from app.infra.audit import AuditWriter
            AuditWriter.get_instance().write(
                actor="hook_engine",
                team_id=payload.get("team_id", ""),
                action="hook:update_status",
                resource_type="hook_rule",
                resource_id=rule["id"],
                details_json=action_config,
            )
            return {"queued": True, "config": action_config}

        return {"unhandled_action": action_type}

    def _invalidate_cache(self) -> None:
        self._rules_cache.clear()
        self._cache_ts = 0.0

    @staticmethod
    def _parse_row(row: dict[str, Any]) -> dict[str, Any]:
        if "action_config_json" in row and isinstance(row["action_config_json"], str):
            try:
                row["action_config_json"] = json.loads(row["action_config_json"])
            except (json.JSONDecodeError, TypeError):
                row["action_config_json"] = {}
        if "enabled" in row:
            row["enabled"] = bool(row["enabled"])
        return row
