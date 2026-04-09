"""F31: Async Audit Writer — non-blocking buffer with periodic flush.

All audit entries are buffered in memory and flushed to the ``audit_logs``
table in batches.  Callers never block on I/O.

Retention: a helper purges entries older than 1 year.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import Database

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_S = 2.0
MAX_BUFFER_SIZE = 500
RETENTION_DAYS = 365


class AuditWriter:
    """Non-blocking audit log writer with internal buffer + periodic flush."""

    _instance: AuditWriter | None = None

    def __init__(self, db: Database | None = None, flush_interval: float = FLUSH_INTERVAL_S):
        self._db = db or Database.get_instance()
        self._buffer: deque[dict[str, Any]] = deque(maxlen=MAX_BUFFER_SIZE * 2)
        self._lock = threading.Lock()
        self._flush_interval = flush_interval
        self._flush_task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls, db: Database | None = None) -> AuditWriter:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance:
            cls._instance.stop()
        cls._instance = None

    # ── Public API ────────────────────────────────────────────────

    def write(
        self,
        *,
        actor: str,
        team_id: str = "",
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        details_json: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue an audit entry (non-blocking)."""
        entry = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "team_id": team_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details_json": json.dumps(details_json or {}, ensure_ascii=False),
        }
        with self._lock:
            self._buffer.append(entry)
        if len(self._buffer) >= MAX_BUFFER_SIZE:
            self._sync_flush()

    def start(self) -> None:
        """Start the background flush loop (call from async context)."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.ensure_future(self._flush_loop())
        logger.info("AuditWriter background flush started (interval=%.1fs)", self._flush_interval)

        from app.skills.sdk import set_audit_sink
        set_audit_sink(self.write)

    def stop(self) -> None:
        """Flush remaining entries and cancel the background task."""
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._sync_flush()

    def flush_now(self) -> int:
        """Synchronous flush — returns the number of entries written."""
        return self._sync_flush()

    # ── Retention ─────────────────────────────────────────────────

    def purge_old_entries(self, retention_days: int = RETENTION_DAYS) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        rows = self._db.execute(
            "DELETE FROM audit_logs WHERE timestamp < ?", (cutoff,)
        )
        count_rows = self._db.execute(
            "SELECT changes() as cnt"
        )
        cnt = count_rows[0]["cnt"] if count_rows else 0
        logger.info("Purged %d audit entries older than %d days", cnt, retention_days)
        return cnt

    # ── Internal ──────────────────────────────────────────────────

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._flush_interval)
            try:
                self._sync_flush()
            except Exception:
                logger.warning("Audit flush error", exc_info=True)

    def _sync_flush(self) -> int:
        with self._lock:
            if not self._buffer:
                return 0
            batch = list(self._buffer)
            self._buffer.clear()

        if not batch:
            return 0

        try:
            cols = list(batch[0].keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_str = ", ".join(cols)
            sql = f"INSERT OR IGNORE INTO audit_logs ({col_str}) VALUES ({placeholders})"
            params_list = [tuple(entry[c] for c in cols) for entry in batch]
            self._db.execute_many(sql, params_list)
            logger.debug("Flushed %d audit entries", len(batch))
            return len(batch)
        except Exception:
            logger.warning("Failed to flush %d audit entries", len(batch), exc_info=True)
            with self._lock:
                self._buffer.extendleft(reversed(batch))
            return 0
