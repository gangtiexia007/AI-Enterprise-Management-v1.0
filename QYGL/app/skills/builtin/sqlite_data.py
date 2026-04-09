"""F13 DATA GATEWAY — the *only* runtime data-access path for agents.

Every query goes through ``DataScopeManager`` for automatic row-level
isolation.  Every write checks the caller's permission level.  Every
operation is audit-logged.

Functions:
    sqlite_data__query   — SELECT with auto-injected scope filters
    sqlite_data__insert  — INSERT with P2+ gate
    sqlite_data__update  — UPDATE with P2+ gate
    sqlite_data__delete  — DELETE with P3+ gate
    sqlite_data__count   — COUNT with auto-injected scope filters
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.data_scope import DataScopeManager
from app.core.database import Database, new_id
from app.core.enums import PermissionLevel, UserTier
from app.core.exceptions import InsufficientPermissionLevel, PermissionDenied, ValidationError
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

WRITABLE_TABLES = {
    "tasks", "task_feedbacks", "escalations", "memories", "conversations",
    "knowledge", "goals", "customers", "customer_contacts", "customer_feedbacks",
    "decision_logs", "kpi_scores",
}

PROTECTED_TABLES = {
    "teams", "team_bots", "sub_agents", "team_skills", "kpi_definitions",
    "employees", "models", "model_usages", "dashboard_users", "skills",
    "team_shadow_config", "shadow_results", "approval_requests",
    "reward_rules", "reward_calculations",
    "hiring_profiles", "interview_templates", "candidates", "onboarding_plans",
    "disputes", "task_dependencies", "dream_reports",
    "hook_rules", "schema_version",
}


def _get_scope(ctx: ToolContext) -> DataScopeManager:
    """Build a DataScopeManager from the team's config when available."""
    db = Database.get_instance()
    team_config: dict[str, Any] = {}
    if ctx.team_id:
        row = db.get_by_id("teams", ctx.team_id)
        if row:
            team_config = row
    return DataScopeManager(team_config)


def _inject_scope_filter(
    ctx: ToolContext,
    scope: DataScopeManager,
    table: str,
    base_sql: str,
    base_params: list[Any],
) -> tuple[str, list[Any]]:
    """Append the DataScope WHERE clause to *base_sql*."""
    where_clause, scope_params = scope.build_filter(
        user_tier=ctx.user_tier,
        team_id=ctx.team_id,
        table=table,
        employee_id=ctx.employee_id,
        department=ctx.department,
    )
    if where_clause:
        joiner = " AND " if "WHERE" in base_sql.upper() else " WHERE "
        base_sql += joiner + where_clause
        base_params.extend(scope_params)
    return base_sql, base_params


def _validate_column(col: str) -> bool:
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col))


def _validate_table(table: str, *, allow_protected: bool = False) -> None:
    if not table or not table.replace("_", "").isalnum():
        raise ValidationError(f"Invalid table name: {table}")
    if not allow_protected and table in PROTECTED_TABLES:
        raise PermissionDenied(f"Table '{table}' is not writable via agent runtime")


# ── Query ─────────────────────────────────────────────────────────────


@tool(permission=PermissionLevel.P0, description="Query rows from a table with automatic scope filtering")
def sqlite_data__query(
    ctx: ToolContext,
    *,
    table: str,
    conditions: dict[str, Any] | None = None,
    order_by: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """SELECT rows from *table* with DataScope filtering auto-injected."""
    _validate_table(table, allow_protected=True)
    db = Database.get_instance()
    scope = _get_scope(ctx)

    if not scope.check_table_access(ctx.user_tier, table):
        raise PermissionDenied(f"Access denied to table '{table}' for tier {ctx.user_tier}")

    sql = f"SELECT * FROM {table}"
    params: list[Any] = []

    if conditions:
        clauses = []
        for k, v in conditions.items():
            if not _validate_column(k):
                raise ValidationError(f"Invalid column name in conditions: {k}")
            if isinstance(v, list):
                ph = ",".join(["?"] * len(v))
                clauses.append(f"{k} IN ({ph})")
                params.extend(v)
            else:
                clauses.append(f"{k} = ?")
                params.append(v)
        sql += " WHERE " + " AND ".join(clauses)

    sql, params = _inject_scope_filter(ctx, scope, table, sql, params)

    if order_by:
        safe_order = "".join(c for c in order_by if c.isalnum() or c in " _,.")
        sql += f" ORDER BY {safe_order}"
    sql += f" LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(sql, tuple(params))
    return [_parse_json_fields(r) for r in rows]


# ── Insert ────────────────────────────────────────────────────────────


@tool(permission=PermissionLevel.P2, description="Insert a new row into a writable table")
def sqlite_data__insert(
    ctx: ToolContext,
    *,
    table: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """INSERT a row.  Requires P2+.  Auto-assigns ``id`` and ``team_id``."""
    _validate_table(table)
    if table not in WRITABLE_TABLES:
        raise PermissionDenied(f"Table '{table}' is not writable")

    db = Database.get_instance()

    if "id" not in data or not data["id"]:
        data["id"] = new_id()
    if "team_id" not in data and ctx.team_id:
        data["team_id"] = ctx.team_id
    if "employee_id" not in data and ctx.employee_id and table in {
        "tasks", "task_feedbacks", "escalations", "memories",
        "conversations", "decision_logs",
    }:
        data["employee_id"] = ctx.employee_id

    record_id = db.insert(table, data)
    row = db.get_by_id(table, record_id)
    return _parse_json_fields(row) if row else {"id": record_id}


# ── Update ────────────────────────────────────────────────────────────


@tool(permission=PermissionLevel.P2, description="Update an existing row in a writable table")
def sqlite_data__update(
    ctx: ToolContext,
    *,
    table: str,
    record_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """UPDATE a row by id.  Requires P2+.  Validates row-level access."""
    _validate_table(table)
    if table not in WRITABLE_TABLES:
        raise PermissionDenied(f"Table '{table}' is not writable")

    db = Database.get_instance()
    scope = _get_scope(ctx)

    existing = db.get_by_id(table, record_id)
    if not existing:
        raise ValidationError(f"Record {record_id} not found in {table}")

    if not scope.check_row_access(ctx.user_tier, existing, ctx.team_id, ctx.employee_id):
        raise PermissionDenied(f"Row-level access denied for {record_id} in {table}")

    data.pop("id", None)
    db.update(table, record_id, data)
    row = db.get_by_id(table, record_id)
    return _parse_json_fields(row) if row else {"id": record_id}


# ── Delete ────────────────────────────────────────────────────────────


@tool(permission=PermissionLevel.P3, description="Delete a row from a writable table (requires P3+)")
def sqlite_data__delete(
    ctx: ToolContext,
    *,
    table: str,
    record_id: str,
) -> dict[str, str]:
    """DELETE a row by id.  Requires P3+ (sensitive operation)."""
    _validate_table(table)
    if table not in WRITABLE_TABLES:
        raise PermissionDenied(f"Table '{table}' is not writable")

    db = Database.get_instance()
    scope = _get_scope(ctx)

    existing = db.get_by_id(table, record_id)
    if not existing:
        raise ValidationError(f"Record {record_id} not found in {table}")

    if not scope.check_row_access(ctx.user_tier, existing, ctx.team_id, ctx.employee_id):
        raise PermissionDenied(f"Row-level access denied for {record_id} in {table}")

    db.delete(table, record_id)
    return {"deleted": record_id, "table": table}


# ── Count ─────────────────────────────────────────────────────────────


@tool(permission=PermissionLevel.P0, description="Count rows in a table with automatic scope filtering")
def sqlite_data__count(
    ctx: ToolContext,
    *,
    table: str,
    conditions: dict[str, Any] | None = None,
) -> dict[str, int]:
    """COUNT matching rows with DataScope filtering auto-injected."""
    _validate_table(table, allow_protected=True)
    db = Database.get_instance()
    scope = _get_scope(ctx)

    if not scope.check_table_access(ctx.user_tier, table):
        raise PermissionDenied(f"Access denied to table '{table}' for tier {ctx.user_tier}")

    sql = f"SELECT COUNT(*) as cnt FROM {table}"
    params: list[Any] = []

    if conditions:
        clauses = []
        for k, v in conditions.items():
            if not _validate_column(k):
                raise ValidationError(f"Invalid column name in conditions: {k}")
            if isinstance(v, list):
                ph = ",".join(["?"] * len(v))
                clauses.append(f"{k} IN ({ph})")
                params.extend(v)
            else:
                clauses.append(f"{k} = ?")
                params.append(v)
        sql += " WHERE " + " AND ".join(clauses)

    sql, params = _inject_scope_filter(ctx, scope, table, sql, params)

    rows = db.execute(sql, tuple(params))
    return {"count": rows[0]["cnt"] if rows else 0}


# ── Helpers ───────────────────────────────────────────────────────────


def _parse_json_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Attempt to deserialize any ``*_json`` columns in the row."""
    if not row:
        return row
    for k, v in list(row.items()):
        if k.endswith("_json") and isinstance(v, str):
            try:
                row[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return row
