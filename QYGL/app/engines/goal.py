"""F19: Goal Manager — hierarchical goal setting, cascading, and progress tracking."""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import new_id
from app.core.enums import GoalLevel, GoalStatus
from app.core.exceptions import ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)


class GoalEngine(EngineBase):
    """Manages goals at company / department / personal levels with cascading."""

    def create_goal(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data.get("owner_id"):
            raise ValidationError("owner_id is required and must not be empty")
        if not data.get("title"):
            raise ValidationError("title is required")

        goal = {
            "id": data.get("id") or new_id(),
            "parent_id": data.get("parent_id", ""),
            "level": data.get("level", GoalLevel.PERSONAL.value),
            "team_id": data.get("team_id", ""),
            "employee_id": data.get("employee_id", ""),
            "owner_id": data["owner_id"],
            "title": data["title"],
            "target_value": data.get("target_value", 0.0),
            "current_value": data.get("current_value", 0.0),
            "unit": data.get("unit", ""),
            "period": data.get("period", ""),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "status": data.get("status", GoalStatus.DRAFT.value),
            "created_at": self._now_iso(),
        }
        self._insert("goals", goal)
        logger.info("Goal created: %s '%s'", goal["id"], goal["title"])
        return goal

    def cascade_goal(
        self,
        parent_goal_id: str,
        sub_goals_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create child goals under a parent, inheriting team_id and period."""
        parent = self._get_by_id("goals", parent_goal_id)
        children: list[dict[str, Any]] = []

        for sg in sub_goals_data:
            sg.setdefault("parent_id", parent_goal_id)
            sg.setdefault("team_id", parent.get("team_id", ""))
            sg.setdefault("period", parent.get("period", ""))
            if not sg.get("owner_id"):
                raise ValidationError(
                    f"owner_id is required for sub-goal '{sg.get('title', '?')}'"
                )
            child = self.create_goal(sg)
            children.append(child)

        if parent["status"] == GoalStatus.DRAFT.value:
            self._update("goals", parent_goal_id, {"status": GoalStatus.ACTIVE.value})

        logger.info(
            "Cascaded %d sub-goals from parent %s", len(children), parent_goal_id
        )
        return children

    def update_progress(
        self, goal_id: str, new_value: float
    ) -> dict[str, Any]:
        goal = self._get_by_id("goals", goal_id)
        updates: dict[str, Any] = {"current_value": new_value}

        if goal["status"] in (GoalStatus.DRAFT.value, GoalStatus.ACTIVE.value):
            updates["status"] = GoalStatus.TRACKING.value

        target = float(goal.get("target_value", 0))
        if target > 0 and new_value >= target:
            updates["status"] = GoalStatus.ACHIEVED.value
            logger.info("Goal achieved: %s", goal_id)

        self._update("goals", goal_id, updates)

        goal.update(updates)
        self._propagate_progress(goal)
        return goal

    def _propagate_progress(self, goal: dict[str, Any]) -> None:
        """Roll up child progress to parent if applicable."""
        parent_id = goal.get("parent_id", "")
        if not parent_id:
            return

        children = self._query("goals", {"parent_id": parent_id})
        if not children:
            return

        total_target = sum(float(c.get("target_value", 0)) for c in children)
        total_current = sum(float(c.get("current_value", 0)) for c in children)

        if total_target > 0:
            parent_progress = round(total_current / total_target * 100, 2)
            parent = self._get_by_id("goals", parent_id)
            parent_target = float(parent.get("target_value", 100))
            mapped_value = round(parent_target * parent_progress / 100, 2)
            self._update("goals", parent_id, {"current_value": mapped_value})

    def list_goals(
        self,
        team_id: str,
        level: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions: dict[str, Any] = {"team_id": team_id}
        if level:
            conditions["level"] = level
        if status:
            conditions["status"] = status
        return self._query("goals", conditions, order_by="created_at DESC", limit=limit)

    def get_goal_tree(self, root_goal_id: str) -> dict[str, Any]:
        """Return a hierarchical tree starting from root_goal_id."""
        root = self._get_by_id("goals", root_goal_id)
        root["children"] = self._build_children(root_goal_id)
        return root

    def _build_children(self, parent_id: str) -> list[dict[str, Any]]:
        children = self._query("goals", {"parent_id": parent_id}, limit=500)
        for child in children:
            child["children"] = self._build_children(child["id"])
        return children
