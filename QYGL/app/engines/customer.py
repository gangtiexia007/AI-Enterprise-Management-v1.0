"""F42: Customer Memory — customer lifecycle, contact records, churn risk detection."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.database import new_id
from app.core.exceptions import ResourceNotFound, ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

CHURN_RISK_DAYS = 30


class CustomerEngine(EngineBase):
    """Manages customer records, contact history, and churn risk analysis."""

    def create_customer(
        self,
        team_id: str,
        name: str,
        company: str = "",
        assigned_employee_id: str = "",
        scope: str = "isolated",
    ) -> dict[str, Any]:
        if not team_id or not name:
            raise ValidationError("team_id and name are required")

        customer = {
            "id": new_id(),
            "team_id": team_id,
            "name": name,
            "company": company,
            "contact_info": "",
            "profile_json": {},
            "assigned_employee_id": assigned_employee_id,
            "scope": scope,
            "status": "active",
            "created_at": self._now_iso(),
        }
        self._insert("customers", customer)
        logger.info("Customer created: %s '%s'", customer["id"], name)
        return customer

    def add_contact_record(
        self,
        customer_id: str,
        employee_id: str,
        content: str,
        contact_type: str = "note",
    ) -> dict[str, Any]:
        self._get_by_id("customers", customer_id)

        record = {
            "id": new_id(),
            "customer_id": customer_id,
            "employee_id": employee_id,
            "content": content,
            "contact_type": contact_type,
            "created_at": self._now_iso(),
        }
        self._insert("customer_contacts", record)
        logger.info("Contact record added for customer %s", customer_id)
        return record

    def add_feedback(
        self,
        customer_id: str,
        feedback_type: str = "general",
        content: str = "",
    ) -> dict[str, Any]:
        self._get_by_id("customers", customer_id)

        feedback = {
            "id": new_id(),
            "customer_id": customer_id,
            "feedback_type": feedback_type,
            "content": content,
            "status": "open",
            "created_at": self._now_iso(),
        }
        self._insert("customer_feedbacks", feedback)
        logger.info("Feedback added for customer %s type=%s", customer_id, feedback_type)
        return feedback

    def transfer_customer(
        self,
        customer_id: str,
        new_employee_id: str,
    ) -> dict[str, Any]:
        customer = self._get_by_id("customers", customer_id)
        old_employee_id = customer.get("assigned_employee_id", "")

        self._update("customers", customer_id, {
            "assigned_employee_id": new_employee_id,
        })

        transfer_note = {
            "id": new_id(),
            "customer_id": customer_id,
            "employee_id": new_employee_id,
            "content": f"客户从 {old_employee_id} 转移至 {new_employee_id}",
            "contact_type": "transfer",
            "created_at": self._now_iso(),
        }
        self._insert("customer_contacts", transfer_note)

        logger.info(
            "Customer %s transferred: %s → %s",
            customer_id, old_employee_id, new_employee_id,
        )
        customer["assigned_employee_id"] = new_employee_id
        return customer

    def get_customer_timeline(
        self, customer_id: str, limit: int = 100
    ) -> dict[str, Any]:
        customer = self._get_by_id("customers", customer_id)

        contacts = self._query(
            "customer_contacts",
            {"customer_id": customer_id},
            order_by="created_at ASC",
            limit=limit,
        )
        feedbacks = self._query(
            "customer_feedbacks",
            {"customer_id": customer_id},
            order_by="created_at ASC",
            limit=limit,
        )

        timeline: list[dict[str, Any]] = []
        for c in contacts:
            timeline.append({
                "type": "contact",
                "subtype": c.get("contact_type", "note"),
                "content": c.get("content", ""),
                "employee_id": c.get("employee_id", ""),
                "timestamp": c.get("created_at", ""),
            })
        for f in feedbacks:
            timeline.append({
                "type": "feedback",
                "subtype": f.get("feedback_type", "general"),
                "content": f.get("content", ""),
                "timestamp": f.get("created_at", ""),
            })

        timeline.sort(key=lambda x: x.get("timestamp", ""))

        return {
            "customer": customer,
            "timeline": timeline,
        }

    def check_churn_risk(self, team_id: str) -> list[dict[str, Any]]:
        """Find customers with no contact in the last CHURN_RISK_DAYS days."""
        cutoff = (datetime.utcnow() - timedelta(days=CHURN_RISK_DAYS)).isoformat()

        customers = self._query("customers", {
            "team_id": team_id, "status": "active",
        }, limit=500)

        at_risk: list[dict[str, Any]] = []
        for cust in customers:
            cid = cust["id"]
            recent = self._execute(
                "SELECT MAX(created_at) as last_contact "
                "FROM customer_contacts WHERE customer_id=?",
                (cid,),
            )
            last_contact = None
            if recent and recent[0].get("last_contact"):
                last_contact = recent[0]["last_contact"]

            if last_contact is None or last_contact < cutoff:
                days_ago = CHURN_RISK_DAYS
                if last_contact:
                    try:
                        lc = datetime.fromisoformat(str(last_contact))
                        days_ago = (datetime.utcnow() - lc).days
                    except (ValueError, TypeError):
                        pass

                at_risk.append({
                    "customer_id": cid,
                    "name": cust.get("name", ""),
                    "company": cust.get("company", ""),
                    "assigned_employee_id": cust.get("assigned_employee_id", ""),
                    "last_contact": last_contact,
                    "days_since_contact": days_ago,
                })

        if at_risk:
            logger.warning(
                "Churn risk: %d customers for team %s", len(at_risk), team_id
            )
        return at_risk
