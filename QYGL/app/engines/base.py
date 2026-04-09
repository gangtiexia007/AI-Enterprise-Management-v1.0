"""Base class for all business engines.

Wraps Database access with audit logging and provides common helpers.
Engines MUST NOT import sqlite3 or execute raw SQL — all data operations
go through the methods defined here.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.core.database import Database, new_id
from app.core.exceptions import ResourceNotFound, ValidationError

logger = logging.getLogger(__name__)


class EngineBase:
    """Base for all business engines. Wraps DB access with audit logging."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database.get_instance()

    # ── Read helpers ──────────────────────────────────────────────

    def _query(
        self,
        table: str,
        conditions: dict[str, Any] | None = None,
        order_by: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self.db.query(table, conditions, order_by=order_by, limit=limit, offset=offset)

    def _get_by_id(self, table: str, record_id: str) -> dict[str, Any]:
        row = self.db.get_by_id(table, record_id)
        if row is None:
            raise ResourceNotFound(table, record_id)
        return row

    def _get_by_id_optional(self, table: str, record_id: str) -> dict[str, Any] | None:
        return self.db.get_by_id(table, record_id)

    def _count(self, table: str, conditions: dict[str, Any] | None = None) -> int:
        return self.db.count(table, conditions)

    def _execute(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        return self.db.execute(sql, params)

    # ── Write helpers ─────────────────────────────────────────────

    def _insert(self, table: str, data: dict[str, Any]) -> str:
        if "id" not in data or not data["id"]:
            data["id"] = new_id()
        record_id = self.db.insert(table, data)
        self._audit("insert", table, record_id, data)
        return record_id

    def _update(self, table: str, record_id: str, data: dict[str, Any]) -> None:
        self.db.update(table, record_id, data)
        self._audit("update", table, record_id, data)

    def _delete(self, table: str, record_id: str) -> None:
        self.db.delete(table, record_id)
        self._audit("delete", table, record_id, {})

    # ── Audit ─────────────────────────────────────────────────────

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any],
        actor: str = "system",
        team_id: str = "",
    ) -> None:
        try:
            self.db.insert(
                "audit_logs",
                {
                    "id": new_id(),
                    "timestamp": datetime.utcnow().isoformat(),
                    "actor": actor,
                    "team_id": team_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "details_json": json.dumps(
                        _safe_serialize(details), ensure_ascii=False
                    ),
                },
            )
        except Exception:
            logger.debug("Audit log write failed (table may not exist yet)", exc_info=True)

    # ── Utility ───────────────────────────────────────────────────

    @staticmethod
    def _new_id() -> str:
        return new_id()

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        """Safely parse a JSON string field from DB into a Python object."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value


def _safe_serialize(obj: Any) -> Any:
    """Convert an object to JSON-safe form for audit logging."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
