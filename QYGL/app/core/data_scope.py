"""F04: Data Scope Manager — table-level + row-level isolation.

Generates WHERE clause fragments that are injected into sqlite_data Skill queries.
T1 (boss) sees everything; T2 (manager) sees department; T3 (employee) sees own data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.enums import UserTier

logger = logging.getLogger(__name__)

SENSITIVE_TABLES = {"models", "dashboard_users"}

EMPLOYEE_SCOPED_TABLES = {
    "tasks", "task_feedbacks", "kpi_scores", "escalations",
    "memories", "conversations", "reward_calculations",
}

TEAM_SCOPED_TABLES = {
    "teams", "team_bots", "sub_agents", "team_skills",
    "kpi_definitions", "goals", "customers", "customer_contacts",
    "customer_feedbacks", "hiring_profiles", "interview_templates",
    "candidates", "onboarding_plans", "reward_rules",
    "team_shadow_config", "shadow_results",
}


class DataScopeManager:

    def __init__(self, team_config: dict[str, Any] | None = None):
        self._scope = {}
        if team_config and "data_scope_json" in team_config:
            scope_data = team_config["data_scope_json"]
            if isinstance(scope_data, str):
                try:
                    scope_data = json.loads(scope_data)
                except (json.JSONDecodeError, TypeError):
                    scope_data = {}
            self._scope = scope_data

    def build_filter(
        self,
        user_tier: str,
        team_id: str,
        table: str,
        employee_id: str = "",
        department: str = "",
    ) -> tuple[str, list[Any]]:
        """Return (WHERE_clause, params) to inject into queries.

        Returns ("", []) if no filtering is needed.
        """
        if user_tier == UserTier.T1:
            return "", []

        clauses: list[str] = []
        params: list[Any] = []

        if table in SENSITIVE_TABLES:
            return "1=0", []

        if table in TEAM_SCOPED_TABLES:
            clauses.append("team_id = ?")
            params.append(team_id)

        if user_tier == UserTier.T3 and table in EMPLOYEE_SCOPED_TABLES:
            if employee_id:
                clauses.append("employee_id = ?")
                params.append(employee_id)

        if user_tier == UserTier.T2 and department:
            if table == "employees":
                clauses.append("department = ?")
                params.append(department)

        row_filters = self._scope.get(table, {}).get("row_filter", [])
        for rf in row_filters:
            col = rf.get("column", "")
            val = rf.get("value", "")
            op = rf.get("op", "=")
            if col and val:
                if op in ("=", "!=", ">", "<", ">=", "<=", "LIKE"):
                    clauses.append(f"{col} {op} ?")
                    params.append(val)

        if not clauses:
            return "", []
        return " AND ".join(clauses), params

    def check_table_access(self, user_tier: str, table: str) -> bool:
        if user_tier == UserTier.T1:
            return True
        if table in SENSITIVE_TABLES and user_tier != UserTier.T1:
            return False
        allowed = self._scope.get("allowed_tables", [])
        if allowed and table not in allowed:
            return False
        return True

    def check_row_access(
        self,
        user_tier: str,
        row: dict[str, Any],
        team_id: str = "",
        employee_id: str = "",
    ) -> bool:
        if user_tier == UserTier.T1:
            return True
        if team_id and row.get("team_id") and row["team_id"] != team_id:
            return False
        if user_tier == UserTier.T3 and employee_id:
            if row.get("employee_id") and row["employee_id"] != employee_id:
                return False
        return True
