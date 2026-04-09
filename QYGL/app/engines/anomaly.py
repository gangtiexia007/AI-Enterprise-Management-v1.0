"""Anomaly detection — flags silent employees and long-overdue tasks as approvals."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import ApprovalType
from app.core.events import Events

logger = logging.getLogger(__name__)


def _emit_approval_submitted(payload: dict[str, Any]) -> None:
    try:
        from app.infra.eventbus import EventBus

        EventBus.get_instance().emit_nowait(Events.APPROVAL_SUBMITTED, payload)
    except Exception:
        logger.debug("Event emit skipped for approval", exc_info=True)


def detect_anomalies(team_ids: list[str] | None = None) -> int:
    """Run anomaly checks and insert ``approval_requests`` (risk_alert). Returns count."""
    db = Database.get_instance()
    anomalies: list[dict[str, Any]] = []
    now = datetime.utcnow()
    three_days_ago = (now - timedelta(days=3)).isoformat()
    two_days_ago = (now - timedelta(days=2)).isoformat()

    sql_silent = """SELECT e.id, e.name, e.team_id, MAX(tf.submitted_at) AS last_feedback
             FROM employees e
             LEFT JOIN task_feedbacks tf ON e.id = tf.employee_id
             WHERE e.status = 'active' AND e.role = 'employee' """
    params_silent: list[Any] = []
    if team_ids:
        ph = ",".join(["?"] * len(team_ids))
        sql_silent += f" AND e.team_id IN ({ph}) "
        params_silent.extend(team_ids)
    sql_silent += """ GROUP BY e.id, e.name, e.team_id
             HAVING last_feedback IS NULL OR last_feedback < ? """
    params_silent.append(three_days_ago)

    silent_employees = db.execute(sql_silent, tuple(params_silent))
    for emp in silent_employees:
        last_fb = emp.get("last_feedback")
        anomalies.append(
            {
                "team_id": emp["team_id"],
                "title": f"{emp['name']}连续3天未提交工作反馈",
                "detail_json": {
                    "kind": "silent_feedback",
                    "employee_id": emp["id"],
                    "employee": emp["name"],
                    "last_feedback": last_fb or "无记录",
                    "days_silent": 3,
                },
                "suggestion": "建议约谈了解情况",
                "reasoning": (
                    f"系统检测到{emp['name']}已超过3天未提交任何工作反馈"
                ),
                "priority": 2,
                "automation_level": "L1",
                "confidence": "B",
                "source_agent": "system/anomaly_detector",
            }
        )

    sql_overdue = (
        "SELECT t.*, e.name AS emp_name FROM tasks t "
        "LEFT JOIN employees e ON t.employee_id = e.id "
        "WHERE t.status = 'overdue' AND t.deadline_at IS NOT NULL "
        "AND t.deadline_at < ?"
    )
    params_od: list[Any] = [two_days_ago]
    if team_ids:
        ph = ",".join(["?"] * len(team_ids))
        sql_overdue += f" AND t.team_id IN ({ph})"
        params_od.extend(team_ids)

    long_overdue = db.execute(sql_overdue, tuple(params_od))
    for task in long_overdue:
        anomalies.append(
            {
                "team_id": task["team_id"],
                "title": f"任务「{task['title']}」已超期超过2天",
                "detail_json": {
                    "kind": "long_overdue_task",
                    "task_id": task["id"],
                    "employee": task.get("emp_name") or "",
                    "task": task["title"],
                    "deadline": task.get("deadline_at") or "",
                },
                "suggestion": "建议重新分配或升级处理",
                "reasoning": "任务严重超期可能影响团队进度",
                "priority": 1,
                "automation_level": "L2",
                "confidence": "A",
                "source_agent": "system/anomaly_detector",
            }
        )

    created = 0
    ts = now.isoformat()
    for a in anomalies:
        row = {
            "id": new_id(),
            "type": ApprovalType.RISK_ALERT.value,
            "team_id": a["team_id"],
            "title": a["title"],
            "detail_json": a["detail_json"],
            "suggestion": a["suggestion"],
            "reasoning": a["reasoning"],
            "priority": a["priority"],
            "automation_level": a["automation_level"],
            "confidence": a["confidence"],
            "status": "pending",
            "source_agent": a["source_agent"],
            "created_at": ts,
        }
        db.insert("approval_requests", row)
        _emit_approval_submitted(
            {
                "team_id": row["team_id"],
                "approval_id": row["id"],
                "title": row["title"],
                "type": row["type"],
            }
        )
        created += 1

    if created:
        logger.info("detect_anomalies: created %d approval request(s)", created)
    return created
