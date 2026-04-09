"""F20: Escalation Engine — multi-level escalation for overdue tasks.

Escalation levels:
  Level 1 (employee) — after configured minutes (default 30)
  Level 2 (manager)  — after configured minutes (default 60)
  Level 3 (boss)     — after configured minutes (default 120), triggers approval gateway

Module function ``check_overdue_tasks`` marks newly overdue tasks, creates initial
escalation rows from team ``escalation_json``, and emits notification events.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import ApprovalType, EscalationLevel, TaskStatus
from app.core.events import Events
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

DEFAULT_INTERVALS = {
    EscalationLevel.EMPLOYEE.value: 30,
    EscalationLevel.MANAGER.value: 60,
    EscalationLevel.BOSS.value: 120,
}


def _emit_sync(event_name: str, payload: dict[str, Any]) -> None:
    try:
        from app.infra.eventbus import EventBus

        EventBus.get_instance().emit_nowait(event_name, payload)
    except Exception:
        logger.debug("Event emit skipped for %s", event_name, exc_info=True)


def check_overdue_tasks(team_ids: list[str] | None = None) -> int:
    """Mark newly overdue tasks, create escalations from team config, emit events.

    Safe for scheduler and manual calls. Uses UTC ISO timestamps for comparisons.
    """
    db = Database.get_instance()
    now = datetime.utcnow().isoformat()

    sql = """SELECT t.*, tm.escalation_json, tm.display_name AS team_name
             FROM tasks t JOIN teams tm ON t.team_id = tm.id
             WHERE t.deadline_at IS NOT NULL AND t.deadline_at < ?
             AND t.status NOT IN ('completed', 'scored', 'overdue')"""
    params: list[Any] = [now]
    if team_ids:
        placeholders = ",".join(["?"] * len(team_ids))
        sql += f" AND t.team_id IN ({placeholders})"
        params.extend(team_ids)

    overdue = db.execute(sql, tuple(params))
    processed = 0

    for task in overdue:
        tid = task["id"]
        team_id = task["team_id"]
        db.update("tasks", tid, {"status": TaskStatus.OVERDUE.value})

        esc_json = task.get("escalation_json", "{}")
        if isinstance(esc_json, str):
            try:
                esc_json = json.loads(esc_json or "{}")
            except (json.JSONDecodeError, TypeError):
                esc_json = {}
        if not isinstance(esc_json, dict):
            esc_json = {}

        notify_employee = esc_json.get("notify_employee_on_overdue", True)
        notify_manager = esc_json.get("notify_manager_on_overdue", True)

        title = task.get("title", "未知任务")
        employee_id = task.get("employee_id") or ""

        _emit_sync(
            Events.TASK_OVERDUE,
            {
                "team_id": team_id,
                "task_id": tid,
                "title": title,
                "employee_id": employee_id,
                "deadline_at": task.get("deadline_at", ""),
            },
        )

        if notify_employee and employee_id:
            emp_esc = {
                "id": new_id(),
                "task_id": tid,
                "level": EscalationLevel.EMPLOYEE.value,
                "target_id": employee_id,
                "message": f"任务「{title}」已超期，请尽快处理",
                "sent_at": now,
            }
            db.insert("escalations", emp_esc)
            _emit_sync(
                Events.ESCALATION_LEVEL1,
                {
                    "team_id": team_id,
                    "task_id": tid,
                    "escalation_id": emp_esc["id"],
                    "target_id": employee_id,
                    "message": emp_esc["message"],
                },
            )

        employee = db.get_by_id("employees", employee_id) if employee_id else None
        if (
            notify_manager
            and employee
            and employee.get("direct_manager_id")
        ):
            mgr_esc = {
                "id": new_id(),
                "task_id": tid,
                "level": EscalationLevel.MANAGER.value,
                "target_id": employee["direct_manager_id"],
                "message": (
                    f"{employee.get('name', '员工')} 的任务「{title}」已超期"
                ),
                "sent_at": now,
            }
            db.insert("escalations", mgr_esc)
            _emit_sync(
                Events.ESCALATION_LEVEL2,
                {
                    "team_id": team_id,
                    "task_id": tid,
                    "escalation_id": mgr_esc["id"],
                    "target_id": mgr_esc["target_id"],
                    "message": mgr_esc["message"],
                },
            )

        processed += 1

    if processed:
        logger.info("check_overdue_tasks: marked %d task(s) overdue", processed)
    return processed


class EscalationEngine(EngineBase):
    """Checks for overdue tasks and creates escalation records at increasing levels."""

    def list_tasks_past_deadline(self, team_id: str) -> list[dict[str, Any]]:
        """Tasks past ``deadline_at`` that are not terminal (for progressive ``escalate``)."""
        now = self._now_iso()
        return self._execute(
            "SELECT * FROM tasks WHERE team_id=? AND deadline_at IS NOT NULL "
            "AND deadline_at < ? "
            "AND status NOT IN (?, ?) ORDER BY deadline_at ASC",
            (team_id, now, TaskStatus.COMPLETED.value, TaskStatus.SCORED.value),
        )

    def check_overdue_tasks(self, team_id: str) -> list[dict[str, Any]]:
        """Deprecated alias for :meth:`list_tasks_past_deadline` (backward compatible)."""
        return self.list_tasks_past_deadline(team_id)

    def escalate(self, task_id: str) -> dict[str, Any] | None:
        """Determine the appropriate escalation level and create a record."""
        task = self._get_by_id("tasks", task_id)
        team_id = task["team_id"]
        employee_id = task.get("employee_id", "")

        intervals = self._get_intervals(team_id)
        deadline_str = task.get("deadline_at")
        if not deadline_str:
            return None

        try:
            deadline = datetime.fromisoformat(str(deadline_str))
        except (ValueError, TypeError):
            return None

        now = datetime.utcnow()
        if now <= deadline:
            return None

        minutes_overdue = (now - deadline).total_seconds() / 60

        existing = self._query(
            "escalations",
            {"task_id": task_id},
            order_by="sent_at DESC",
            limit=10,
        )
        existing_levels = {e["level"] for e in existing}

        level = self._determine_level(minutes_overdue, intervals, existing_levels)
        if level is None:
            return None

        target_id = self._resolve_target(level, employee_id, team_id)
        message = self._build_message(level, task, minutes_overdue)

        record = {
            "id": new_id(),
            "task_id": task_id,
            "level": level,
            "target_id": target_id,
            "message": message,
            "sent_at": self._now_iso(),
        }
        self._insert("escalations", record)

        if level == EscalationLevel.BOSS.value:
            self._submit_boss_approval(task, record)

        logger.info(
            "Escalation %s → level=%s target=%s", task_id, level, target_id
        )
        return record

    def get_escalation_history(self, task_id: str) -> list[dict[str, Any]]:
        return self._query(
            "escalations",
            {"task_id": task_id},
            order_by="sent_at ASC",
        )

    # ── Internal helpers ──────────────────────────────────────────

    def _get_intervals(self, team_id: str) -> dict[str, int]:
        team = self._get_by_id_optional("teams", team_id)
        if not team:
            return dict(DEFAULT_INTERVALS)

        esc_json = team.get("escalation_json", "{}")
        if isinstance(esc_json, str):
            try:
                esc_json = json.loads(esc_json)
            except (json.JSONDecodeError, TypeError):
                esc_json = {}

        if not isinstance(esc_json, dict):
            esc_json = {}

        return {
            EscalationLevel.EMPLOYEE.value: esc_json.get(
                "level1_minutes", DEFAULT_INTERVALS[EscalationLevel.EMPLOYEE.value]
            ),
            EscalationLevel.MANAGER.value: esc_json.get(
                "level2_minutes", DEFAULT_INTERVALS[EscalationLevel.MANAGER.value]
            ),
            EscalationLevel.BOSS.value: esc_json.get(
                "level3_minutes", DEFAULT_INTERVALS[EscalationLevel.BOSS.value]
            ),
        }

    def _determine_level(
        self,
        minutes_overdue: float,
        intervals: dict[str, int],
        existing_levels: set[str],
    ) -> str | None:
        levels_ordered = [
            (EscalationLevel.BOSS.value, intervals[EscalationLevel.BOSS.value]),
            (EscalationLevel.MANAGER.value, intervals[EscalationLevel.MANAGER.value]),
            (EscalationLevel.EMPLOYEE.value, intervals[EscalationLevel.EMPLOYEE.value]),
        ]

        for level, threshold in levels_ordered:
            if minutes_overdue >= threshold and level not in existing_levels:
                return level

        return None

    def _resolve_target(self, level: str, employee_id: str, team_id: str) -> str:
        if level == EscalationLevel.EMPLOYEE.value:
            return employee_id

        if level == EscalationLevel.MANAGER.value and employee_id:
            emp = self._get_by_id_optional("employees", employee_id)
            if emp and emp.get("direct_manager_id"):
                return emp["direct_manager_id"]

        team = self._get_by_id_optional("teams", team_id)
        return team.get("id", "") if team else ""

    def _build_message(
        self, level: str, task: dict[str, Any], minutes_overdue: float
    ) -> str:
        hours = round(minutes_overdue / 60, 1)
        title = task.get("title", "未知任务")
        return (
            f"【{level.upper()}级预警】任务「{title}」已逾期 {hours} 小时，"
            f"请及时处理。任务ID: {task['id']}"
        )

    def _submit_boss_approval(
        self, task: dict[str, Any], escalation: dict[str, Any]
    ) -> None:
        import asyncio
        try:
            from app.safety.approval import ApprovalGateway
            gateway = ApprovalGateway.get_instance()
            coro = gateway.submit(
                action_type=ApprovalType.ESCALATION_BOSS.value,
                team_id=task.get("team_id", ""),
                title=f"任务逾期升级 — {task.get('title', '')}",
                detail={
                    "task_id": task["id"],
                    "escalation_id": escalation["id"],
                    "employee_id": task.get("employee_id", ""),
                },
                confidence="B",
                source_agent="escalation_engine",
                reasoning=f"任务已逾期并升级到老板级别",
            )
            try:
                loop = asyncio.get_running_loop()
                asyncio.ensure_future(coro)
            except RuntimeError:
                asyncio.run(coro)
        except Exception:
            logger.error("Failed to submit boss approval via gateway", exc_info=True)
