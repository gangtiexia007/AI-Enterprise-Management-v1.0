"""F17: Task Engine — create, dispatch, score, and complete tasks.

Scoring uses three dimensions:
  - Timeliness (40%): based on deadline vs actual completion time
  - Quality (40%): LLM evaluation of feedback content (placeholder for V1)
  - Complexity (20%): configurable multiplier per template
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.core.database import new_id
from app.core.enums import TaskStatus
from app.core.events import Events
from app.core.exceptions import ResourceNotFound, StateTransitionError, ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

SCORE_WEIGHT_TIMELINESS = 0.40
SCORE_WEIGHT_QUALITY = 0.40
SCORE_WEIGHT_COMPLEXITY = 0.20


class TaskEngine(EngineBase):
    """Orchestrates the full task lifecycle."""

    # ── Create ────────────────────────────────────────────────────

    def create_task(
        self,
        team_id: str,
        title: str,
        description: str = "",
        employee_id: str = "",
        deadline: str | None = None,
        template_id: str = "",
    ) -> dict[str, Any]:
        if not team_id or not title:
            raise ValidationError("team_id and title are required")

        task_data = {
            "id": new_id(),
            "team_id": team_id,
            "title": title,
            "description": description,
            "employee_id": employee_id,
            "template_id": template_id,
            "status": TaskStatus.PENDING.value,
            "deadline_at": deadline,
            "created_at": self._now_iso(),
        }
        self._insert("tasks", task_data)
        logger.info("Task created: %s for team %s", task_data["id"], team_id)
        return task_data

    # ── Dispatch ──────────────────────────────────────────────────

    def dispatch_task(self, task_id: str) -> dict[str, Any]:
        task = self._get_by_id("tasks", task_id)
        current = task["status"]
        if current not in (TaskStatus.PENDING.value,):
            raise StateTransitionError("Task", current, TaskStatus.DISPATCHED.value)

        now = self._now_iso()
        self._update("tasks", task_id, {
            "status": TaskStatus.DISPATCHED.value,
            "dispatched_at": now,
        })
        task["status"] = TaskStatus.DISPATCHED.value
        task["dispatched_at"] = now
        logger.info("Task dispatched: %s", task_id)
        return task

    # ── Submit Feedback ───────────────────────────────────────────

    def submit_feedback(
        self,
        task_id: str,
        employee_id: str,
        content: str,
        feedback_type: str = "text",
    ) -> dict[str, Any]:
        task = self._get_by_id("tasks", task_id)
        if task["status"] not in (
            TaskStatus.DISPATCHED.value,
            TaskStatus.IN_PROGRESS.value,
        ):
            raise StateTransitionError("Task", task["status"], "feedback submission")

        if task["status"] == TaskStatus.DISPATCHED.value:
            self._update("tasks", task_id, {"status": TaskStatus.IN_PROGRESS.value})

        fb = {
            "id": new_id(),
            "task_id": task_id,
            "employee_id": employee_id,
            "content": content,
            "feedback_type": feedback_type,
            "submitted_at": self._now_iso(),
        }
        self._insert("task_feedbacks", fb)

        self._update("tasks", task_id, {"status": TaskStatus.SUBMITTED.value})
        logger.info("Feedback submitted for task %s by %s", task_id, employee_id)
        return fb

    # ── Score ─────────────────────────────────────────────────────

    def score_task(self, task_id: str) -> dict[str, Any]:
        """Three-dimensional scoring: timeliness(40%) + quality(40%) + complexity(20%)."""
        task = self._get_by_id("tasks", task_id)
        if task["status"] not in (TaskStatus.SUBMITTED.value, TaskStatus.IN_PROGRESS.value):
            raise StateTransitionError("Task", task["status"], TaskStatus.SCORED.value)

        timeliness = self._calc_timeliness(task)
        quality = self._calc_quality(task_id)
        complexity_multiplier = self._get_complexity_multiplier(task.get("template_id", ""))

        raw = (
            timeliness * SCORE_WEIGHT_TIMELINESS
            + quality * SCORE_WEIGHT_QUALITY
            + 100.0 * SCORE_WEIGHT_COMPLEXITY
        )
        final_score = round(raw * complexity_multiplier, 2)
        grade = self._score_to_grade(final_score)

        self._update("tasks", task_id, {
            "status": TaskStatus.SCORED.value,
            "score": final_score,
            "score_timeliness": round(timeliness, 2),
            "score_quality": round(quality, 2),
            "score_complexity": round(complexity_multiplier, 2),
            "grade": grade,
        })

        result = {
            "task_id": task_id,
            "score_timeliness": round(timeliness, 2),
            "score_quality": round(quality, 2),
            "score_complexity": round(complexity_multiplier, 2),
            "final_score": final_score,
            "grade": grade,
        }
        logger.info("Task scored: %s → %.2f (%s)", task_id, final_score, grade)
        return result

    def _calc_timeliness(self, task: dict[str, Any]) -> float:
        deadline_str = task.get("deadline_at")
        if not deadline_str:
            return 100.0

        try:
            deadline = datetime.fromisoformat(str(deadline_str))
        except (ValueError, TypeError):
            return 100.0

        completed_str = task.get("completed_at") or self._now_iso()
        try:
            completed = datetime.fromisoformat(str(completed_str))
        except (ValueError, TypeError):
            completed = datetime.utcnow()

        if completed <= deadline:
            return 100.0

        hours_late = (completed - deadline).total_seconds() / 3600
        penalty = min(hours_late * 5, 60)
        return max(100.0 - penalty, 40.0)

    def _calc_quality(self, task_id: str) -> float:
        """Placeholder: LLM evaluation of feedback content. Returns 80.0 for V1."""
        return 80.0

    def _get_complexity_multiplier(self, template_id: str) -> float:
        if not template_id:
            return 1.0
        tpl = self._get_by_id_optional("task_templates", template_id)
        if tpl and "complexity" in tpl:
            try:
                return float(tpl["complexity"])
            except (ValueError, TypeError):
                pass
        return 1.0

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    # ── Complete ──────────────────────────────────────────────────

    def complete_task(self, task_id: str) -> dict[str, Any]:
        task = self._get_by_id("tasks", task_id)
        if task["status"] not in (TaskStatus.SCORED.value,):
            raise StateTransitionError("Task", task["status"], TaskStatus.COMPLETED.value)

        now = self._now_iso()
        self._update("tasks", task_id, {
            "status": TaskStatus.COMPLETED.value,
            "completed_at": now,
        })
        task["status"] = TaskStatus.COMPLETED.value
        task["completed_at"] = now

        try:
            from app.engines.cross_team import CrossTeamEngine
            ct = CrossTeamEngine()
            unblocked = ct.on_task_completed(task_id)
            if unblocked:
                logger.info("Task %s completion unblocked %d downstream tasks", task_id, len(unblocked))
        except Exception as e:
            logger.warning("CrossTeam check failed for task %s: %s", task_id, e)

        logger.info("Task completed: %s", task_id)
        return task

    # ── Query ─────────────────────────────────────────────────────

    def list_tasks(
        self,
        team_id: str,
        status: str | None = None,
        employee_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions: dict[str, Any] = {"team_id": team_id}
        if status:
            conditions["status"] = status
        if employee_id:
            conditions["employee_id"] = employee_id
        return self._query("tasks", conditions, order_by="created_at DESC", limit=limit)

    def get_overdue_tasks(self, team_id: str) -> list[dict[str, Any]]:
        now = self._now_iso()
        rows = self._execute(
            "SELECT * FROM tasks WHERE team_id=? AND deadline_at < ? "
            "AND status NOT IN (?, ?) ORDER BY deadline_at ASC",
            (team_id, now, TaskStatus.COMPLETED.value, TaskStatus.SCORED.value),
        )
        return rows
