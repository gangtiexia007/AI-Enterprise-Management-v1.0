"""F46: Dispute Center — employee challenge & resolution workflow.

Employees can dispute AI-generated KPI scores, task quality assessments,
reward calculations, or risk labels.  Every dispute preserves the original
AI data, reasoning chain, and human-submitted evidence for full audit trail.

Resolution flow:  filed → evidence_collected → ruling → resolved / overturned
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import DisputeStatus, DisputeType
from app.core.events import Events
from app.core.exceptions import ResourceNotFound, ValidationError

logger = logging.getLogger(__name__)


async def _publish(event: str, data: dict[str, Any]) -> None:
    try:
        from app.infra.eventbus import EventBus
        bus = EventBus.get_instance()
        await bus.emit(event, data)
    except Exception as e:
        logger.warning("EventBus publish failed for %s: %s", event, e)


class DisputeCenter:
    """Service for filing, collecting evidence, and resolving disputes."""

    _instance: DisputeCenter | None = None

    def __init__(self, db: Database | None = None):
        self.db = db or Database.get_instance()

    @classmethod
    def get_instance(cls, db: Database | None = None) -> DisputeCenter:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Filing ────────────────────────────────────────────────────

    async def file_dispute(
        self,
        employee_id: str,
        dispute_type: str,
        target_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Create a new dispute.

        ``target_id`` references the disputed entity (KPI score id, task id, etc.).
        The method automatically snapshots the original AI data and reasoning
        from the target record for audit purposes.
        """
        if dispute_type not in [dt.value for dt in DisputeType]:
            raise ValidationError(f"Invalid dispute type: {dispute_type}")

        original_data, ai_reasoning, team_id = self._snapshot_target(
            dispute_type, target_id,
        )

        dispute_id = new_id()
        now = datetime.now(timezone.utc).isoformat()

        self.db.insert("disputes", {
            "id": dispute_id,
            "type": dispute_type,
            "team_id": team_id,
            "employee_id": employee_id,
            "target_type": self._target_table(dispute_type),
            "target_id": target_id,
            "original_data_json": original_data,
            "ai_reasoning": ai_reasoning,
            "employee_reason": reason,
            "evidence_json": [],
            "status": DisputeStatus.FILED,
            "created_at": now,
        })

        await _publish(Events.DISPUTE_FILED, {
            "dispute_id": dispute_id,
            "team_id": team_id,
            "employee_id": employee_id,
            "dispute_type": dispute_type,
            "target_id": target_id,
        })

        logger.info(
            "Dispute filed: %s by employee %s against %s %s",
            dispute_id, employee_id, dispute_type, target_id,
        )
        return self.db.get_by_id("disputes", dispute_id)

    # ── Evidence ──────────────────────────────────────────────────

    async def add_evidence(
        self,
        dispute_id: str,
        evidence_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Append evidence to a dispute.

        ``evidence_data`` should contain at minimum:
            - type: "text" | "file" | "screenshot" | "data_export"
            - content: the evidence payload or reference
            - submitted_by: who added it
        """
        dispute = self._get_dispute_or_raise(dispute_id)
        if dispute["status"] in (DisputeStatus.RESOLVED, DisputeStatus.OVERTURNED):
            raise ValidationError(
                f"Dispute {dispute_id} is already {dispute['status']}, cannot add evidence"
            )

        existing_evidence = dispute.get("evidence_json", [])
        if isinstance(existing_evidence, str):
            try:
                existing_evidence = json.loads(existing_evidence)
            except (json.JSONDecodeError, TypeError):
                existing_evidence = []

        evidence_data["added_at"] = datetime.now(timezone.utc).isoformat()
        evidence_data["evidence_id"] = new_id()
        existing_evidence.append(evidence_data)

        new_status = dispute["status"]
        if new_status == DisputeStatus.FILED:
            new_status = DisputeStatus.EVIDENCE_COLLECTED

        self.db.update("disputes", dispute_id, {
            "evidence_json": existing_evidence,
            "status": new_status,
        })

        logger.info("Evidence added to dispute %s (now %d items)", dispute_id, len(existing_evidence))
        return self.db.get_by_id("disputes", dispute_id)

    # ── Query ─────────────────────────────────────────────────────

    def list_disputes(
        self,
        team_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List disputes for a team, optionally filtered by status."""
        conditions: dict[str, Any] = {"team_id": team_id}
        if status is not None:
            conditions["status"] = status
        rows = self.db.query(
            "disputes", conditions, order_by="created_at DESC",
        )
        return [self._parse_json_fields(r) for r in rows]

    def get_dispute_with_evidence(self, dispute_id: str) -> dict[str, Any]:
        """Full dispute detail including original data, AI reasoning, evidence."""
        dispute = self._get_dispute_or_raise(dispute_id)
        dispute = self._parse_json_fields(dispute)

        target_table = dispute.get("target_type", "")
        target_id = dispute.get("target_id", "")
        if target_table and target_id:
            current = self.db.get_by_id(target_table, target_id)
            dispute["current_target_data"] = current
        else:
            dispute["current_target_data"] = None

        return dispute

    # ── Resolution ────────────────────────────────────────────────

    async def resolve(
        self,
        dispute_id: str,
        resolution: str,
        resolver_id: str,
    ) -> dict[str, Any]:
        """Mark a dispute as resolved (original decision upheld, possibly with adjustments)."""
        dispute = self._get_dispute_or_raise(dispute_id)
        if dispute["status"] in (DisputeStatus.RESOLVED, DisputeStatus.OVERTURNED):
            raise ValidationError(
                f"Dispute {dispute_id} is already {dispute['status']}"
            )

        now = datetime.now(timezone.utc).isoformat()
        self.db.update("disputes", dispute_id, {
            "status": DisputeStatus.RESOLVED,
            "resolution": resolution,
            "resolver_id": resolver_id,
            "resolved_at": now,
        })

        await _publish(Events.DISPUTE_RESOLVED, {
            "dispute_id": dispute_id,
            "team_id": dispute.get("team_id", ""),
            "employee_id": dispute.get("employee_id", ""),
            "resolution": resolution,
            "resolver_id": resolver_id,
        })

        logger.info("Dispute %s resolved by %s", dispute_id, resolver_id)
        return self.db.get_by_id("disputes", dispute_id)

    async def overturn(
        self,
        dispute_id: str,
        reason: str,
        resolver_id: str,
    ) -> dict[str, Any]:
        """Overturn the original AI decision — the employee's challenge is accepted."""
        dispute = self._get_dispute_or_raise(dispute_id)
        if dispute["status"] in (DisputeStatus.RESOLVED, DisputeStatus.OVERTURNED):
            raise ValidationError(
                f"Dispute {dispute_id} is already {dispute['status']}"
            )

        now = datetime.now(timezone.utc).isoformat()
        self.db.update("disputes", dispute_id, {
            "status": DisputeStatus.OVERTURNED,
            "resolution": reason,
            "resolver_id": resolver_id,
            "resolved_at": now,
        })

        await _publish(Events.DISPUTE_OVERTURNED, {
            "dispute_id": dispute_id,
            "team_id": dispute.get("team_id", ""),
            "employee_id": dispute.get("employee_id", ""),
            "reason": reason,
            "resolver_id": resolver_id,
        })

        logger.info("Dispute %s overturned by %s: %s", dispute_id, resolver_id, reason)
        return self.db.get_by_id("disputes", dispute_id)

    # ── Rule Correction Suggestion ────────────────────────────────

    async def suggest_rule_correction(self, dispute_id: str) -> dict[str, Any]:
        """Analyze dispute patterns and suggest rule changes.

        This method inspects the dispute's type, original data, evidence,
        and resolution to produce a structured suggestion that can be
        reviewed by a manager before applying to the scoring/reward rules.

        In a full implementation, this would call the LLM with the dispute
        context.  For now, it generates a deterministic suggestion based
        on dispute metadata.
        """
        dispute = self.get_dispute_with_evidence(dispute_id)
        dispute_type = dispute.get("type", "")
        original_data = dispute.get("original_data_json", {})
        evidence = dispute.get("evidence_json", [])
        resolution = dispute.get("resolution", "")

        similar = self.db.query(
            "disputes",
            {"team_id": dispute.get("team_id", ""), "type": dispute_type},
            order_by="created_at DESC",
            limit=50,
        )

        overturned_count = sum(
            1 for d in similar if d.get("status") == DisputeStatus.OVERTURNED
        )
        total_similar = len(similar)
        overturn_rate = overturned_count / total_similar if total_similar else 0.0

        suggestion: dict[str, Any] = {
            "dispute_id": dispute_id,
            "dispute_type": dispute_type,
            "pattern_analysis": {
                "total_similar_disputes": total_similar,
                "overturned_count": overturned_count,
                "overturn_rate": round(overturn_rate, 4),
            },
            "suggested_action": "no_change",
            "detail": "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if overturn_rate >= 0.5 and total_similar >= 3:
            suggestion["suggested_action"] = "revise_rule"
            suggestion["detail"] = (
                f"High overturn rate ({overturn_rate:.0%}) across {total_similar} "
                f"similar '{dispute_type}' disputes.  "
                f"Review the scoring/calculation rules for this category.  "
                f"Latest resolution: {resolution}"
            )
        elif overturn_rate >= 0.3:
            suggestion["suggested_action"] = "review_threshold"
            suggestion["detail"] = (
                f"Moderate overturn rate ({overturn_rate:.0%}).  "
                f"Consider adjusting confidence thresholds for '{dispute_type}'."
            )
        else:
            suggestion["detail"] = (
                f"Overturn rate is low ({overturn_rate:.0%}).  "
                f"Current rules appear adequate for '{dispute_type}'."
            )

        self.db.update("disputes", dispute_id, {
            "rule_correction_suggestion": json.dumps(suggestion, ensure_ascii=False),
        })

        logger.info(
            "Rule correction suggestion for dispute %s: %s",
            dispute_id, suggestion["suggested_action"],
        )
        return suggestion

    # ── Internals ─────────────────────────────────────────────────

    def _get_dispute_or_raise(self, dispute_id: str) -> dict[str, Any]:
        row = self.db.get_by_id("disputes", dispute_id)
        if not row:
            raise ResourceNotFound("Dispute", dispute_id)
        return row

    def _snapshot_target(
        self, dispute_type: str, target_id: str,
    ) -> tuple[dict[str, Any], str, str]:
        """Fetch the original data and AI reasoning from the disputed entity."""
        table = self._target_table(dispute_type)
        row = self.db.get_by_id(table, target_id)
        if row is None:
            return {}, "", ""

        original_data: dict[str, Any] = dict(row)
        ai_reasoning = ""
        team_id = row.get("team_id", "")

        if dispute_type == DisputeType.KPI_SCORE:
            ai_reasoning = row.get("feedback", "")
            scores_json = row.get("scores_json", {})
            if isinstance(scores_json, str):
                try:
                    scores_json = json.loads(scores_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            original_data["scores_json"] = scores_json

        elif dispute_type == DisputeType.TASK_QUALITY:
            ai_reasoning = row.get("feedback", "")

        elif dispute_type == DisputeType.REWARD:
            ai_reasoning = row.get("formula_used", "")
            variables = row.get("variables_json", {})
            if isinstance(variables, str):
                try:
                    variables = json.loads(variables)
                except (json.JSONDecodeError, TypeError):
                    pass
            original_data["variables_json"] = variables

        elif dispute_type == DisputeType.RISK_LABEL:
            ai_reasoning = row.get("reasoning", row.get("message", ""))

        return original_data, ai_reasoning, team_id

    @staticmethod
    def _target_table(dispute_type: str) -> str:
        """Map dispute type to the source database table."""
        mapping = {
            DisputeType.KPI_SCORE:    "kpi_scores",
            DisputeType.TASK_QUALITY: "tasks",
            DisputeType.REWARD:       "reward_calculations",
            DisputeType.RISK_LABEL:   "escalations",
        }
        return mapping.get(dispute_type, "")

    @staticmethod
    def _parse_json_fields(row: dict[str, Any]) -> dict[str, Any]:
        for field in ("original_data_json", "evidence_json", "shadow_data_json"):
            if field in row and isinstance(row[field], str):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        if "rule_correction_suggestion" in row and isinstance(row["rule_correction_suggestion"], str):
            if row["rule_correction_suggestion"]:
                try:
                    row["rule_correction_suggestion"] = json.loads(row["rule_correction_suggestion"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row
