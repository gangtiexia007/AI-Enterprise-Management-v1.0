"""F26: Event-Driven Notification System — smart merging + channel routing.

Subscribes to EventBus events and decides how to notify users.
Important messages are sent immediately; normal ones are batched per
5-minute window and merged before delivery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from app.core.enums import Channel
from app.core.events import Events

logger = logging.getLogger(__name__)

MERGE_WINDOW_S = 300

IMPORTANT_EVENTS = frozenset({
    Events.ESCALATION_LEVEL2,
    Events.ESCALATION_LEVEL3,
    Events.APPROVAL_SUBMITTED,
    Events.APPROVAL_EXPIRED,
    Events.TASK_OVERDUE,
    Events.KPI_DISPUTED,
    Events.DISPUTE_FILED,
    Events.CUSTOMER_CHURN_WARNING,
    Events.MODEL_BUDGET_EXCEEDED,
    Events.EMPLOYEE_CONTRACT_EXPIRING,
})

EVENT_TEMPLATES: dict[str, str] = {
    Events.TASK_DISPATCHED: "📋 新任务已分配: {title}",
    Events.TASK_SUBMITTED: "✅ 任务已提交: {title}",
    Events.TASK_SCORED: "📊 任务已评分: {title} — {grade}",
    Events.TASK_OVERDUE: "⚠️ 任务超期: {title}",
    Events.TASK_COMPLETED: "🎉 任务已完成: {title}",
    Events.KPI_SCORED: "📈 KPI 评分完成: {employee_name}",
    Events.APPROVAL_SUBMITTED: "🔔 新审批请求: {title}",
    Events.APPROVAL_APPROVED: "✅ 审批已通过: {title}",
    Events.APPROVAL_REJECTED: "❌ 审批已驳回: {title}",
    Events.ESCALATION_LEVEL1: "📢 升级提醒 (L1): {message}",
    Events.ESCALATION_LEVEL2: "🚨 升级提醒 (L2): {message}",
    Events.ESCALATION_LEVEL3: "🔴 升级到老板 (L3): {message}",
    Events.DISPUTE_FILED: "⚖️ 新申诉提交: {employee_name}",
    Events.REWARD_CALCULATED: "💰 薪酬已计算: {employee_name}",
    Events.GOAL_ACHIEVED: "🏆 目标达成: {title}",
    Events.CUSTOMER_FEEDBACK: "💬 客户反馈: {customer_name}",
    Events.EMPLOYEE_BIRTHDAY: "🎂 员工生日: {employee_name}",
    Events.EMPLOYEE_CONTRACT_EXPIRING: "📄 合同即将到期: {employee_name}",
}


class NotificationService:
    """Central notification service that listens to EventBus and dispatches."""

    _instance: NotificationService | None = None

    def __init__(self):
        self._pending: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._flush_task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> NotificationService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self) -> None:
        """Register with EventBus and start the merge-flush loop."""
        if self._running:
            return
        self._running = True

        from app.infra.eventbus import EventBus
        bus = EventBus.get_instance()
        bus.subscribe_all(self._on_event)

        self._flush_task = asyncio.ensure_future(self._flush_loop())
        logger.info("NotificationService started")

    def stop(self) -> None:
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

    async def _on_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Handle an incoming event from the EventBus."""
        template = EVENT_TEMPLATES.get(event_name)
        if not template:
            return

        try:
            message = template.format_map(defaultdict(str, payload))
        except Exception:
            message = f"{event_name}: {payload}"

        recipient_id = self._resolve_recipient(event_name, payload)
        if not recipient_id:
            return

        team_id = payload.get("team_id", "")
        is_important = event_name in IMPORTANT_EVENTS

        if is_important:
            channel = self._resolve_channel(team_id, recipient_id)
            await self._send(channel, team_id, recipient_id, message)
            logger.info("Immediate notification: %s → %s", event_name, recipient_id)
        else:
            key = f"{team_id}:{recipient_id}"
            self._pending[key].append({
                "message": message,
                "event": event_name,
                "team_id": team_id,
                "recipient_id": recipient_id,
                "timestamp": time.time(),
            })

    async def _flush_loop(self) -> None:
        """Periodically flush pending normal notifications."""
        while self._running:
            await asyncio.sleep(MERGE_WINDOW_S)
            try:
                await self._flush_pending()
            except Exception:
                logger.error("Notification flush error", exc_info=True)

    async def _flush_pending(self) -> None:
        keys = list(self._pending.keys())
        for key in keys:
            items = self._pending.pop(key, [])
            if not items:
                continue

            team_id = items[0]["team_id"]
            recipient_id = items[0]["recipient_id"]
            channel = self._resolve_channel(team_id, recipient_id)

            if len(items) == 1:
                await self._send(channel, team_id, recipient_id, items[0]["message"])
            else:
                header = f"📋 {len(items)} 条通知合并:\n"
                merged = header + "\n".join(f"• {it['message']}" for it in items)
                await self._send(channel, team_id, recipient_id, merged)

                from app.infra.eventbus import EventBus
                EventBus.get_instance().emit_nowait(
                    Events.NOTIFICATION_MERGED,
                    {"team_id": team_id, "recipient_id": recipient_id, "count": len(items)},
                )

    @staticmethod
    async def _send(channel: str, team_id: str, recipient_id: str, content: str) -> None:
        """Dispatch a notification to the appropriate channel."""
        if channel == Channel.FEISHU:
            from app.skills.builtin.feishu_im import _send_feishu_message
            await _send_feishu_message(team_id, recipient_id, content)
        elif channel == Channel.WECOM:
            from app.skills.builtin.wecom_im import _send_wecom_message
            await _send_wecom_message(team_id, recipient_id, content)
        else:
            logger.debug("Dashboard notification for %s: %s", recipient_id, content[:50])

    @staticmethod
    def _resolve_recipient(event_name: str, payload: dict[str, Any]) -> str:
        """Determine who should receive this notification."""
        if payload.get("approver_id"):
            return payload["approver_id"]
        if payload.get("employee_id"):
            return payload["employee_id"]
        if payload.get("target_id"):
            return payload["target_id"]
        if payload.get("manager_id"):
            return payload["manager_id"]
        return ""

    @staticmethod
    def _resolve_channel(team_id: str, employee_id: str) -> str:
        """Determine which channel to use for this employee's team."""
        if not team_id:
            return Channel.DASHBOARD
        try:
            from app.core.database import Database
            db = Database.get_instance()
            bots = db.query("team_bots", {"team_id": team_id, "enabled": True}, limit=1)
            if bots:
                return bots[0].get("channel", Channel.FEISHU)
        except Exception:
            pass
        return Channel.FEISHU
