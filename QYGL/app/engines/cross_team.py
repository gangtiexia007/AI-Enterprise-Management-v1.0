"""F43: Cross-Team Dependency Engine — track inter-task dependencies and unblock flows."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.core.database import new_id
from app.core.enums import TaskStatus
from app.core.exceptions import ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)


class CrossTeamEngine(EngineBase):
    """Manages upstream/downstream task dependencies across teams."""

    def create_dependency(
        self,
        upstream_task_id: str,
        downstream_task_id: str,
        dependency_type: str = "finish_to_start",
    ) -> dict[str, Any]:
        if upstream_task_id == downstream_task_id:
            raise ValidationError("A task cannot depend on itself")

        self._get_by_id("tasks", upstream_task_id)
        self._get_by_id("tasks", downstream_task_id)

        existing = self._query("task_dependencies", {
            "upstream_task_id": upstream_task_id,
            "downstream_task_id": downstream_task_id,
        })
        if existing:
            return existing[0]

        dep = {
            "id": new_id(),
            "upstream_task_id": upstream_task_id,
            "downstream_task_id": downstream_task_id,
            "dependency_type": dependency_type,
            "status": "waiting",
            "created_at": self._now_iso(),
        }
        self._insert("task_dependencies", dep)
        logger.info(
            "Dependency created: %s → %s", upstream_task_id, downstream_task_id
        )
        return dep

    def check_dependencies(self, task_id: str) -> dict[str, Any]:
        """Check if a task is blocked by unfinished upstream dependencies."""
        deps = self._query("task_dependencies", {"downstream_task_id": task_id})
        if not deps:
            return {"task_id": task_id, "blocked": False, "blocking_tasks": []}

        blocking: list[dict[str, Any]] = []
        for dep in deps:
            if dep["status"] == "waiting":
                upstream = self._get_by_id_optional("tasks", dep["upstream_task_id"])
                if upstream and upstream["status"] != TaskStatus.COMPLETED.value:
                    blocking.append({
                        "upstream_task_id": dep["upstream_task_id"],
                        "upstream_status": upstream["status"],
                        "title": upstream.get("title", ""),
                    })

        return {
            "task_id": task_id,
            "blocked": len(blocking) > 0,
            "blocking_tasks": blocking,
        }

    def on_task_completed(self, task_id: str) -> list[dict[str, Any]]:
        """When an upstream task completes, resolve its dependencies and unblock downstream."""
        deps = self._query("task_dependencies", {
            "upstream_task_id": task_id,
            "status": "waiting",
        })

        unblocked: list[dict[str, Any]] = []
        now = self._now_iso()

        for dep in deps:
            self._update("task_dependencies", dep["id"], {
                "status": "resolved",
            })

            downstream_id = dep["downstream_task_id"]
            remaining = self._check_remaining_blockers(downstream_id)

            if not remaining:
                self._update("tasks", downstream_id, {
                    "blocked_reason": "",
                    "unblocked_at": now,
                })
                downstream = self._get_by_id("tasks", downstream_id)
                unblocked.append(downstream)
                logger.info("Task unblocked: %s", downstream_id)

        logger.info(
            "Task %s completed → %d downstream tasks unblocked",
            task_id, len(unblocked),
        )
        return unblocked

    def _check_remaining_blockers(self, task_id: str) -> list[dict[str, Any]]:
        return self._query("task_dependencies", {
            "downstream_task_id": task_id,
            "status": "waiting",
        })

    def get_bottleneck_report(self, team_id: str) -> list[dict[str, Any]]:
        """Identify tasks that are blocking the most downstream work."""
        all_deps = self._execute(
            "SELECT td.*, t.title, t.status, t.team_id "
            "FROM task_dependencies td "
            "JOIN tasks t ON t.id = td.upstream_task_id "
            "WHERE td.status = 'waiting' AND t.team_id = ?",
            (team_id,),
        )

        block_counts: dict[str, dict[str, Any]] = {}
        for dep in all_deps:
            uid = dep["upstream_task_id"]
            if uid not in block_counts:
                block_counts[uid] = {
                    "task_id": uid,
                    "title": dep.get("title", ""),
                    "status": dep.get("status", ""),
                    "blocked_downstream_count": 0,
                    "downstream_task_ids": [],
                }
            block_counts[uid]["blocked_downstream_count"] += 1
            block_counts[uid]["downstream_task_ids"].append(dep["downstream_task_id"])

        result = sorted(
            block_counts.values(),
            key=lambda x: x["blocked_downstream_count"],
            reverse=True,
        )
        return result

    def list_dependencies(
        self, team_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT td.* FROM task_dependencies td "
            "JOIN tasks t ON t.id = td.upstream_task_id "
            "WHERE t.team_id = ? ORDER BY td.created_at DESC LIMIT ?",
            (team_id, limit),
        )
