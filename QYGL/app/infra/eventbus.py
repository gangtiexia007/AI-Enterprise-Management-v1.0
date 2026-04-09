"""F29: EventBus — asyncio.Queue-based pub/sub with persistent critical events.

All event names MUST come from ``app.core.events.Events``.
Subscribers register callbacks; the bus dispatches asynchronously.
Critical events (approvals, escalations, etc.) are persisted to ``audit_logs``.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from app.core.events import Events

logger = logging.getLogger(__name__)

Callback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]

CRITICAL_EVENT_PREFIXES = (
    "approval.", "escalation.", "dispute.", "shadow.", "reward.",
    "team.disabled", "employee.resigned",
)


class EventBus:
    """In-process async event bus with fan-out to subscribers."""

    _instance: EventBus | None = None

    def __init__(self, max_queue_size: int = 10_000):
        self._queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(
            maxsize=max_queue_size,
        )
        self._subscribers: dict[str, list[Callback]] = defaultdict(list)
        self._wildcard_subscribers: list[Callback] = []
        self._dispatch_task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> EventBus:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance:
            cls._instance.stop()
        cls._instance = None

    # ── Pub ───────────────────────────────────────────────────────

    async def emit(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Publish an event. Non-blocking unless the queue is full."""
        data = payload or {}
        data.setdefault("_ts", datetime.now(timezone.utc).isoformat())
        data.setdefault("_event", event_name)
        await self._queue.put((event_name, data))
        logger.debug("Event emitted: %s", event_name)

    def emit_nowait(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Fire-and-forget emit (drops if queue full)."""
        data = payload or {}
        data.setdefault("_ts", datetime.now(timezone.utc).isoformat())
        data.setdefault("_event", event_name)
        try:
            self._queue.put_nowait((event_name, data))
        except asyncio.QueueFull:
            logger.warning("EventBus queue full, dropping event: %s", event_name)

    # ── Sub ───────────────────────────────────────────────────────

    def subscribe(self, event_name: str, callback: Callback) -> None:
        """Subscribe to a specific event name."""
        self._subscribers[event_name].append(callback)
        logger.debug("Subscriber added for %s", event_name)

    def subscribe_all(self, callback: Callback) -> None:
        """Subscribe to every event (wildcard)."""
        self._wildcard_subscribers.append(callback)

    def subscribe_prefix(self, prefix: str, callback: Callback) -> None:
        """Subscribe to all events matching a prefix (e.g., ``task.``)."""
        self._subscribers[f"__prefix__{prefix}"].append(callback)

    def unsubscribe(self, event_name: str, callback: Callback) -> None:
        if callback in self._subscribers.get(event_name, []):
            self._subscribers[event_name].remove(callback)

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.ensure_future(self._dispatch_loop())
        logger.info("EventBus dispatch loop started")

    def stop(self) -> None:
        self._running = False
        if self._dispatch_task and not self._dispatch_task.done():
            self._dispatch_task.cancel()

    # ── Dispatch ──────────────────────────────────────────────────

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event_name, payload = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0,
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                continue

            if self._is_critical(event_name):
                self._persist_critical(event_name, payload)

            callbacks = list(self._subscribers.get(event_name, []))
            for key, subs in self._subscribers.items():
                if key.startswith("__prefix__") and event_name.startswith(key[10:]):
                    callbacks.extend(subs)
            callbacks.extend(self._wildcard_subscribers)

            for cb in callbacks:
                try:
                    await cb(event_name, payload)
                except Exception:
                    logger.error(
                        "EventBus subscriber error for %s", event_name, exc_info=True,
                    )

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _is_critical(event_name: str) -> bool:
        return any(event_name.startswith(p) for p in CRITICAL_EVENT_PREFIXES)

    @staticmethod
    def _persist_critical(event_name: str, payload: dict[str, Any]) -> None:
        try:
            from app.infra.audit import AuditWriter
            writer = AuditWriter.get_instance()
            writer.write(
                actor=payload.get("actor", "system"),
                team_id=payload.get("team_id", ""),
                action=f"event:{event_name}",
                resource_type="event",
                resource_id=event_name,
                details_json={k: v for k, v in payload.items() if not k.startswith("_")},
            )
        except Exception:
            logger.debug("Could not persist critical event %s", event_name, exc_info=True)
