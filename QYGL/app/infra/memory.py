"""F27: 5-Layer Memory System with scenario-based dispatch.

Layers::

    L1 — System rules (hard constraints, never overridden)
    L2 — Team SOP / operational rules
    L3 — Employee profile & action cards
    L4 — Business knowledge / case studies
    L5 — Conversation summaries / dialogue memory

The ``MemoryDispatcher`` loads the right layers for each of the 9 defined
scenarios, attaching auditable metadata to every entry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import MemoryLayer, MemoryScenario

logger = logging.getLogger(__name__)

# ── Scenario × Layer Dispatch Table ──────────────────────────────────

SCENARIO_LAYERS: dict[str, list[str]] = {
    MemoryScenario.DAILY_CHAT: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3, MemoryLayer.L5,
    ],
    MemoryScenario.KPI_SCORING: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3, MemoryLayer.L4,
    ],
    MemoryScenario.TASK_ESCALATION: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3,
    ],
    MemoryScenario.COACHING: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3, MemoryLayer.L4, MemoryLayer.L5,
    ],
    MemoryScenario.REPORT_GENERATION: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L4,
    ],
    MemoryScenario.RISK_WARNING: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3, MemoryLayer.L4,
    ],
    MemoryScenario.CUSTOMER_INQUIRY: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3, MemoryLayer.L4, MemoryLayer.L5,
    ],
    MemoryScenario.APPROVAL_PROCESSING: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3,
    ],
    MemoryScenario.DISPUTE_PROCESSING: [
        MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3, MemoryLayer.L4,
    ],
}

MAX_ENTRIES_PER_LAYER = 50


class MemoryDispatcher:
    """Load and write memory entries across the 5-layer stack."""

    _instance: MemoryDispatcher | None = None

    def __init__(self, db: Database | None = None):
        self._db = db or Database.get_instance()

    @classmethod
    def get_instance(cls, db: Database | None = None) -> MemoryDispatcher:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Core Dispatch ─────────────────────────────────────────────

    def load_for_scenario(
        self,
        scenario: str,
        role: str = "",
        team_id: str = "",
        employee_id: str = "",
    ) -> dict[str, list[dict[str, Any]]]:
        """Return ``{layer: [memory_entries]}`` for the given scenario.

        Only the layers relevant to *scenario* are loaded.
        Each entry carries auditable metadata.
        """
        layers = SCENARIO_LAYERS.get(scenario, [MemoryLayer.L1, MemoryLayer.L5])
        result: dict[str, list[dict[str, Any]]] = {}

        for layer in layers:
            entries = self._load_layer(layer, team_id, employee_id)
            self._touch_references(entries)
            result[layer] = entries

        logger.debug(
            "Memory loaded: scenario=%s, layers=%d, total=%d",
            scenario, len(result), sum(len(v) for v in result.values()),
        )
        return result

    # ── CRUD ──────────────────────────────────────────────────────

    def add_memory(
        self,
        *,
        layer: str,
        content: str,
        team_id: str = "",
        employee_id: str = "",
        source: str = "",
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
        is_verified: bool = False,
        expires_at: str | None = None,
    ) -> str:
        """Insert a new memory entry with auditable metadata."""
        mem_id = new_id()
        self._db.insert("memories", {
            "id": mem_id,
            "layer": layer,
            "team_id": team_id,
            "employee_id": employee_id,
            "content": content,
            "metadata_json": metadata or {},
            "source": source,
            "created_by": created_by,
            "reference_count": 0,
            "last_referenced_at": None,
            "is_verified": is_verified,
            "expires_at": expires_at,
        })
        logger.debug("Memory added: %s (layer=%s, team=%s)", mem_id, layer, team_id)
        return mem_id

    def update_memory(self, memory_id: str, **fields: Any) -> None:
        for k in ("metadata_json",):
            if k in fields and isinstance(fields[k], (dict, list)):
                fields[k] = json.dumps(fields[k], ensure_ascii=False)
        self._db.update("memories", memory_id, fields)

    def delete_memory(self, memory_id: str) -> None:
        self._db.delete("memories", memory_id)

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        row = self._db.get_by_id("memories", memory_id)
        return self._parse_row(row) if row else None

    def search_memories(
        self,
        layer: str | None = None,
        team_id: str | None = None,
        employee_id: str | None = None,
        keyword: str = "",
        limit: int = MAX_ENTRIES_PER_LAYER,
    ) -> list[dict[str, Any]]:
        """Full-text keyword search across memories."""
        conditions: dict[str, Any] = {}
        if layer:
            conditions["layer"] = layer
        if team_id:
            conditions["team_id"] = team_id
        if employee_id:
            conditions["employee_id"] = employee_id

        if keyword:
            sql = "SELECT * FROM memories WHERE content LIKE ?"
            params: list[Any] = [f"%{keyword}%"]
            if layer:
                sql += " AND layer = ?"
                params.append(layer)
            if team_id:
                sql += " AND team_id = ?"
                params.append(team_id)
            if employee_id:
                sql += " AND employee_id = ?"
                params.append(employee_id)
            sql += f" ORDER BY created_at DESC LIMIT {limit}"
            rows = self._db.execute(sql, tuple(params))
        else:
            rows = self._db.query(
                "memories", conditions or None,
                order_by="created_at DESC", limit=limit,
            )

        return [self._parse_row(r) for r in rows]

    def summarize_and_compact(self, team_id: str, employee_id: str = "") -> int:
        """Remove expired and low-reference L5 entries (conversation memory GC)."""
        now = datetime.now(timezone.utc).isoformat()
        sql = (
            "DELETE FROM memories WHERE layer = ? AND team_id = ? "
            "AND (expires_at IS NOT NULL AND expires_at < ?)"
        )
        params: tuple = (MemoryLayer.L5, team_id, now)
        self._db.execute(sql, params)
        count_rows = self._db.execute("SELECT changes() as cnt")
        cnt = count_rows[0]["cnt"] if count_rows else 0
        logger.info("Compacted %d expired L5 memories for team %s", cnt, team_id)
        return cnt

    # ── Internals ─────────────────────────────────────────────────

    def _load_layer(
        self,
        layer: str,
        team_id: str,
        employee_id: str,
    ) -> list[dict[str, Any]]:
        """Load memory entries for one layer with appropriate scoping."""
        conditions: dict[str, Any] = {"layer": layer}

        if layer in (MemoryLayer.L1,):
            pass
        elif layer in (MemoryLayer.L2, MemoryLayer.L4):
            if team_id:
                conditions["team_id"] = team_id
        elif layer == MemoryLayer.L3:
            if employee_id:
                conditions["employee_id"] = employee_id
            elif team_id:
                conditions["team_id"] = team_id
        elif layer == MemoryLayer.L5:
            if employee_id:
                conditions["employee_id"] = employee_id
            elif team_id:
                conditions["team_id"] = team_id

        rows = self._db.query(
            "memories", conditions,
            order_by="created_at DESC",
            limit=MAX_ENTRIES_PER_LAYER,
        )
        return [self._parse_row(r) for r in rows]

    def _touch_references(self, entries: list[dict[str, Any]]) -> None:
        """Bump ``reference_count`` and ``last_referenced_at`` for loaded entries."""
        now = datetime.now(timezone.utc).isoformat()
        for entry in entries:
            mid = entry.get("id")
            if mid:
                try:
                    self._db.execute(
                        "UPDATE memories SET reference_count = reference_count + 1, "
                        "last_referenced_at = ? WHERE id = ?",
                        (now, mid),
                    )
                except Exception:
                    pass

    @staticmethod
    def _parse_row(row: dict[str, Any]) -> dict[str, Any]:
        if "metadata_json" in row and isinstance(row["metadata_json"], str):
            try:
                row["metadata_json"] = json.loads(row["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                row["metadata_json"] = {}
        if "is_verified" in row:
            row["is_verified"] = bool(row["is_verified"])
        return row
