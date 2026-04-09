"""F03: Employee Manager — CRUD, transfer, sender_id identification, retention reminders."""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import EmployeeStatus
from app.core.exceptions import EmployeeNotFound, ValidationError

logger = logging.getLogger(__name__)


class EmployeeManager:

    def __init__(self, db: Database | None = None):
        self.db = db or Database.get_instance()

    def create_employee(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data.get("name"):
            raise ValidationError("Employee name is required")

        emp_id = data.get("id") or new_id()
        record = {
            "id": emp_id,
            "name": data["name"],
            "feishu_id": data.get("feishu_id", ""),
            "wecom_id": data.get("wecom_id", ""),
            "team_id": data.get("team_id", ""),
            "role": data.get("role", "employee"),
            "department": data.get("department", ""),
            "status": EmployeeStatus.ACTIVE,
            "direct_manager_id": data.get("direct_manager_id", ""),
            "join_date": data.get("join_date"),
            "birthday": data.get("birthday"),
            "contract_end_date": data.get("contract_end_date"),
            "notes": data.get("notes", ""),
        }
        self.db.insert("employees", record)
        logger.info("Employee created: %s (%s)", emp_id, data["name"])
        return self.get_employee(emp_id)

    def get_employee(self, employee_id: str) -> dict[str, Any]:
        row = self.db.get_by_id("employees", employee_id)
        if not row:
            raise EmployeeNotFound(employee_id)
        return row

    def update_employee(self, employee_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.get_employee(employee_id)
        self.db.update("employees", employee_id, data)
        return self.get_employee(employee_id)

    def list_employees(
        self,
        team_id: str | None = None,
        department: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: dict[str, Any] = {}
        if team_id:
            conditions["team_id"] = team_id
        if department:
            conditions["department"] = department
        if status:
            conditions["status"] = status
        return self.db.query("employees", conditions or None, order_by="name")

    def identify_by_sender(self, channel: str, sender_id: str) -> dict[str, Any] | None:
        if channel == "feishu":
            rows = self.db.query("employees", {"feishu_id": sender_id}, limit=1)
        elif channel == "wecom":
            rows = self.db.query("employees", {"wecom_id": sender_id}, limit=1)
        else:
            return None
        return rows[0] if rows else None

    def transfer(self, employee_id: str, new_team_id: str) -> dict[str, Any]:
        emp = self.get_employee(employee_id)
        old_team = emp.get("team_id", "")
        self.db.update("employees", employee_id, {
            "status": EmployeeStatus.TRANSFERRING,
        })
        self.db.update("employees", employee_id, {
            "team_id": new_team_id,
            "status": EmployeeStatus.ACTIVE,
        })
        logger.info("Employee %s transferred: %s → %s", employee_id, old_team, new_team_id)
        return self.get_employee(employee_id)

    def resign(self, employee_id: str) -> dict[str, Any]:
        self.get_employee(employee_id)
        self.db.update("employees", employee_id, {"status": EmployeeStatus.RESIGNED})
        return self.get_employee(employee_id)

    def get_retention_alerts(self) -> list[dict[str, Any]]:
        """Return employees with upcoming birthdays, anniversaries, or expiring contracts."""
        sql = """
            SELECT * FROM employees
            WHERE status = 'active'
            AND (
                (birthday IS NOT NULL AND
                 strftime('%m-%d', birthday) BETWEEN
                 strftime('%m-%d', 'now') AND strftime('%m-%d', 'now', '+7 days'))
                OR
                (contract_end_date IS NOT NULL AND
                 date(contract_end_date) BETWEEN date('now') AND date('now', '+30 days'))
                OR
                (join_date IS NOT NULL AND
                 strftime('%m-%d', join_date) BETWEEN
                 strftime('%m-%d', 'now') AND strftime('%m-%d', 'now', '+7 days'))
            )
        """
        return self.db.execute(sql)
