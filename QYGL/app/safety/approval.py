"""F44: Approval Gateway — 4-tier automation with confidence-based downgrade.

This is the central choke-point for every AI-initiated action.
All Engines and Agents call ``ApprovalGateway.submit()`` before side-effects.
Shadow mode interception happens here, *before* any real execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import (
    ApprovalStatus,
    ApprovalType,
    AutomationLevel,
    AutomationProfile,
    Confidence,
    ShadowMode,
)
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


# ── Result value object ──────────────────────────────────────────────

@dataclass
class ApprovalResult:
    status: str                            # notified | pending | executed | auto_executed | shadow_recorded
    approval_id: str | None = None
    shadow_id: str | None = None
    effective_level: str = ""              # final AutomationLevel after downgrade
    detail: dict[str, Any] = field(default_factory=dict)


# ── Per-action-type default automation levels ────────────────────────
# More sensitive actions default to lower automation regardless of profile.

_ACTION_LEVEL_OVERRIDES: dict[str, AutomationLevel] = {
    ApprovalType.TEAM_CREATE:          AutomationLevel.L2,
    ApprovalType.EMPLOYEE_TRANSFER:    AutomationLevel.L2,
    ApprovalType.KPI_SCORE:            AutomationLevel.L2,
    ApprovalType.REWARD_CALC:          AutomationLevel.L2,
    ApprovalType.ESCALATION_BOSS:      AutomationLevel.L1,
    ApprovalType.RISK_ALERT:           AutomationLevel.L1,
}

_PROFILE_BASE_LEVEL: dict[str, AutomationLevel] = {
    AutomationProfile.STARTUP:        AutomationLevel.L1,
    AutomationProfile.MID_MANAGER:    AutomationLevel.L2,
    AutomationProfile.PROCESS_DRIVEN: AutomationLevel.L3,
}

# Timeout in minutes per approval type; used when L2 creates a pending record.
_TIMEOUT_MINUTES: dict[str, int] = {
    ApprovalType.TASK_DISPATCH:         60,
    ApprovalType.KPI_SCORE:            120,
    ApprovalType.REWARD_CALC:          180,
    ApprovalType.GOAL_SPLIT:            60,
    ApprovalType.TEAM_CREATE:          240,
    ApprovalType.EMPLOYEE_TRANSFER:    480,
    ApprovalType.KNOWLEDGE_CANDIDATE:   60,
    ApprovalType.RISK_ALERT:            30,
    ApprovalType.ESCALATION_BOSS:       30,
    ApprovalType.CROSS_TEAM_TRIGGER:    60,
    ApprovalType.COACHING_SUGGESTION:   60,
}
_DEFAULT_TIMEOUT_MINUTES = 120


# ══════════════════════════════════════════════════════════════════════
# ApprovalGateway
# ══════════════════════════════════════════════════════════════════════

class ApprovalGateway:
    """Singleton service — callable from any Engine or Agent."""

    _instance: ApprovalGateway | None = None

    def __init__(self, db: Database | None = None):
        self.db = db or Database.get_instance()

    @classmethod
    def get_instance(cls, db: Database | None = None) -> ApprovalGateway:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Public API ────────────────────────────────────────────────

    async def submit(
        self,
        action_type: str,
        team_id: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
    ) -> ApprovalResult:
        """Central entry-point.  Every AI action flows through here."""

        # 1. Shadow mode check — must come first
        if self._is_shadow_mode(team_id):
            return await self._handle_shadow(
                team_id, action_type, title, detail, confidence, source_agent, reasoning,
            )

        # 2. Resolve effective automation level
        effective_level = self._resolve_level(team_id, action_type, confidence)

        # 3. Route by tier
        if effective_level == AutomationLevel.L1:
            return await self._handle_l1(
                action_type, team_id, title, detail, confidence, source_agent, reasoning,
            )
        if effective_level == AutomationLevel.L2:
            return await self._handle_l2(
                action_type, team_id, title, detail, confidence, source_agent, reasoning,
            )
        if effective_level == AutomationLevel.L3:
            return await self._handle_l3(
                action_type, team_id, title, detail, confidence, source_agent, reasoning,
            )
        # L4
        return await self._handle_l4(
            action_type, team_id, title, detail, confidence, source_agent, reasoning,
        )

    async def approve(self, approval_id: str, approver_id: str) -> dict[str, Any]:
        """Manager approves a pending request."""
        record = self._get_approval_or_raise(approval_id)
        if record["status"] != ApprovalStatus.PENDING:
            raise ValidationError(
                f"Approval {approval_id} is '{record['status']}', cannot approve"
            )

        now = datetime.now(timezone.utc).isoformat()
        self.db.update("approval_requests", approval_id, {
            "status": ApprovalStatus.APPROVED,
            "approver_id": approver_id,
            "resolved_at": now,
        })

        await _publish(Events.APPROVAL_APPROVED, {
            "approval_id": approval_id,
            "team_id": record["team_id"],
            "type": record["type"],
            "approver_id": approver_id,
        })

        logger.info("Approval %s approved by %s", approval_id, approver_id)
        return self.db.get_by_id("approval_requests", approval_id)

    async def reject(
        self, approval_id: str, approver_id: str, reason: str = "",
    ) -> dict[str, Any]:
        """Manager rejects a pending request."""
        record = self._get_approval_or_raise(approval_id)
        if record["status"] != ApprovalStatus.PENDING:
            raise ValidationError(
                f"Approval {approval_id} is '{record['status']}', cannot reject"
            )

        now = datetime.now(timezone.utc).isoformat()
        self.db.update("approval_requests", approval_id, {
            "status": ApprovalStatus.REJECTED,
            "approver_id": approver_id,
            "rejection_reason": reason,
            "resolved_at": now,
        })

        await _publish(Events.APPROVAL_REJECTED, {
            "approval_id": approval_id,
            "team_id": record["team_id"],
            "type": record["type"],
            "approver_id": approver_id,
            "reason": reason,
        })

        logger.info("Approval %s rejected by %s: %s", approval_id, approver_id, reason)
        return self.db.get_by_id("approval_requests", approval_id)

    async def withdraw(self, approval_id: str) -> dict[str, Any]:
        """Source agent or admin cancels a pending request."""
        record = self._get_approval_or_raise(approval_id)
        if record["status"] != ApprovalStatus.PENDING:
            raise ValidationError(
                f"Approval {approval_id} is '{record['status']}', cannot withdraw"
            )

        now = datetime.now(timezone.utc).isoformat()
        self.db.update("approval_requests", approval_id, {
            "status": ApprovalStatus.WITHDRAWN,
            "resolved_at": now,
        })

        await _publish(Events.APPROVAL_WITHDRAWN, {
            "approval_id": approval_id,
            "team_id": record["team_id"],
            "type": record["type"],
        })

        logger.info("Approval %s withdrawn", approval_id)
        return self.db.get_by_id("approval_requests", approval_id)

    def list_pending(self, team_id: str) -> list[dict[str, Any]]:
        """All pending approvals for a team, newest first."""
        return self.db.query(
            "approval_requests",
            {"team_id": team_id, "status": ApprovalStatus.PENDING},
            order_by="created_at DESC",
        )

    def get_stats(self, team_id: str) -> dict[str, int]:
        """Approval counts by status for a team."""
        stats: dict[str, int] = {}
        for st in ApprovalStatus:
            stats[st.value] = self.db.count(
                "approval_requests",
                {"team_id": team_id, "status": st.value},
            )
        stats["total"] = sum(stats.values())
        return stats

    async def expire_stale(self) -> int:
        """Mark approvals past their timeout as expired.  Called by scheduler."""
        now = datetime.now(timezone.utc)
        pending = self.db.query(
            "approval_requests",
            {"status": ApprovalStatus.PENDING},
            order_by="created_at ASC",
            limit=500,
        )
        expired_count = 0
        for rec in pending:
            created = _parse_dt(rec["created_at"])
            action_type = rec["type"]
            timeout = timedelta(
                minutes=_TIMEOUT_MINUTES.get(action_type, _DEFAULT_TIMEOUT_MINUTES),
            )
            if now - created > timeout:
                self.db.update("approval_requests", rec["id"], {
                    "status": ApprovalStatus.EXPIRED,
                    "resolved_at": now.isoformat(),
                })
                await _publish(Events.APPROVAL_EXPIRED, {
                    "approval_id": rec["id"],
                    "team_id": rec["team_id"],
                    "type": action_type,
                })
                expired_count += 1
        if expired_count:
            logger.info("Expired %d stale approvals", expired_count)
        return expired_count

    # ── Tier handlers ─────────────────────────────────────────────

    async def _handle_shadow(
        self,
        team_id: str,
        action_type: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
    ) -> ApprovalResult:
        """Shadow mode: record what *would have* happened, execute nothing."""
        effective_level = self._resolve_level(team_id, action_type, confidence)
        shadow_id = new_id()
        self.db.insert("shadow_results", {
            "id": shadow_id,
            "team_id": team_id,
            "result_type": action_type,
            "original_action_json": {
                "title": title,
                "detail": detail,
                "source_agent": source_agent,
                "reasoning": reasoning,
            },
            "shadow_data_json": {
                "effective_level": effective_level,
                "would_have_created_approval": effective_level in (AutomationLevel.L1, AutomationLevel.L2),
                "would_have_auto_executed": effective_level in (AutomationLevel.L3, AutomationLevel.L4),
            },
            "confidence": confidence,
            "would_have_done": (
                f"[{effective_level}] {title}"
            ),
        })
        logger.info(
            "Shadow recorded %s for team %s (would-be %s)", shadow_id, team_id, effective_level,
        )
        return ApprovalResult(
            status="shadow_recorded",
            shadow_id=shadow_id,
            effective_level=effective_level,
            detail={"team_id": team_id, "action_type": action_type},
        )

    async def _handle_l1(
        self,
        action_type: str,
        team_id: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
    ) -> ApprovalResult:
        """L1: Notify only — send information, no approval record."""
        record_id = self._persist_request(
            action_type, team_id, title, detail, confidence,
            source_agent, reasoning, AutomationLevel.L1,
            status=ApprovalStatus.APPROVED,
        )

        await _publish(Events.NOTIFICATION_SENT, {
            "team_id": team_id,
            "type": "approval_l1_notify",
            "title": title,
            "action_type": action_type,
            "source_agent": source_agent,
        })

        logger.info("L1 notify — %s for team %s", action_type, team_id)
        return ApprovalResult(
            status="notified",
            approval_id=record_id,
            effective_level=AutomationLevel.L1,
            detail={"action_type": action_type, "title": title},
        )

    async def _handle_l2(
        self,
        action_type: str,
        team_id: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
    ) -> ApprovalResult:
        """L2: Create pending approval and wait for human decision."""
        record_id = self._persist_request(
            action_type, team_id, title, detail, confidence,
            source_agent, reasoning, AutomationLevel.L2,
            status=ApprovalStatus.PENDING,
        )

        timeout = _TIMEOUT_MINUTES.get(action_type, _DEFAULT_TIMEOUT_MINUTES)

        await _publish(Events.APPROVAL_SUBMITTED, {
            "approval_id": record_id,
            "team_id": team_id,
            "type": action_type,
            "title": title,
            "confidence": confidence,
            "timeout_minutes": timeout,
            "source_agent": source_agent,
        })

        logger.info("L2 pending — %s for team %s (id=%s)", action_type, team_id, record_id)
        return ApprovalResult(
            status="pending",
            approval_id=record_id,
            effective_level=AutomationLevel.L2,
            detail={
                "action_type": action_type,
                "title": title,
                "timeout_minutes": timeout,
            },
        )

    async def _handle_l3(
        self,
        action_type: str,
        team_id: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
    ) -> ApprovalResult:
        """L3: Auto-execute first, then send a report notification."""
        record_id = self._persist_request(
            action_type, team_id, title, detail, confidence,
            source_agent, reasoning, AutomationLevel.L3,
            status=ApprovalStatus.APPROVED,
        )

        await _publish(Events.APPROVAL_APPROVED, {
            "approval_id": record_id,
            "team_id": team_id,
            "type": action_type,
            "title": title,
            "auto_executed": True,
            "source_agent": source_agent,
        })

        await _publish(Events.NOTIFICATION_SENT, {
            "team_id": team_id,
            "type": "approval_l3_report",
            "title": f"[Auto-executed] {title}",
            "approval_id": record_id,
        })

        logger.info("L3 auto-execute — %s for team %s (id=%s)", action_type, team_id, record_id)
        return ApprovalResult(
            status="executed",
            approval_id=record_id,
            effective_level=AutomationLevel.L3,
            detail={"action_type": action_type, "title": title},
        )

    async def _handle_l4(
        self,
        action_type: str,
        team_id: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
    ) -> ApprovalResult:
        """L4: Full auto — execute silently, no notification."""
        record_id = self._persist_request(
            action_type, team_id, title, detail, confidence,
            source_agent, reasoning, AutomationLevel.L4,
            status=ApprovalStatus.APPROVED,
        )

        await _publish(Events.APPROVAL_APPROVED, {
            "approval_id": record_id,
            "team_id": team_id,
            "type": action_type,
            "auto_executed": True,
            "silent": True,
        })

        logger.info("L4 silent auto — %s for team %s (id=%s)", action_type, team_id, record_id)
        return ApprovalResult(
            status="auto_executed",
            approval_id=record_id,
            effective_level=AutomationLevel.L4,
            detail={"action_type": action_type, "title": title},
        )

    # ── Level resolution ──────────────────────────────────────────

    def _resolve_level(
        self, team_id: str, action_type: str, confidence: str,
    ) -> AutomationLevel:
        """Determine effective automation level after profile + confidence rules."""
        base = self._get_team_automation_level(team_id, action_type)
        return self._apply_confidence_downgrade(base, confidence)

    def _get_team_automation_level(
        self, team_id: str, action_type: str,
    ) -> AutomationLevel:
        """Look up team profile → base level, then apply per-action overrides.

        The *stricter* (lower) level always wins.
        """
        team = self.db.get_by_id("teams", team_id)
        if not team:
            return AutomationLevel.L2  # safe default

        profile = team.get("automation_profile", AutomationProfile.STARTUP)
        profile_level = _PROFILE_BASE_LEVEL.get(profile, AutomationLevel.L1)
        action_override = _ACTION_LEVEL_OVERRIDES.get(action_type)

        if action_override is None:
            return profile_level

        return min(profile_level, action_override, key=_level_rank)

    @staticmethod
    def _apply_confidence_downgrade(
        level: AutomationLevel, confidence: str,
    ) -> AutomationLevel:
        """Low confidence forces auto-execution tiers down.

        Rules:
          - C + L4 → L3  (low confidence must not run silently)
          - C + L3 → L2  (low confidence must not auto-execute)
          - LLM self-assessment can never upgrade C → A
        """
        if confidence == Confidence.C:
            if level == AutomationLevel.L4:
                return AutomationLevel.L3
            if level == AutomationLevel.L3:
                return AutomationLevel.L2
        return level

    # ── Shadow mode check ─────────────────────────────────────────

    def _is_shadow_mode(self, team_id: str) -> bool:
        rows = self.db.query("team_shadow_config", {"team_id": team_id}, limit=1)
        if not rows:
            return False
        return rows[0].get("mode") == ShadowMode.SHADOW

    # ── Persistence helpers ───────────────────────────────────────

    def _persist_request(
        self,
        action_type: str,
        team_id: str,
        title: str,
        detail: dict[str, Any],
        confidence: str,
        source_agent: str,
        reasoning: str,
        automation_level: AutomationLevel,
        status: ApprovalStatus,
    ) -> str:
        record_id = new_id()
        now = datetime.now(timezone.utc).isoformat()
        resolved_at = now if status != ApprovalStatus.PENDING else None

        data: dict[str, Any] = {
            "id": record_id,
            "type": action_type,
            "team_id": team_id,
            "title": title,
            "detail_json": detail,
            "reasoning": reasoning,
            "automation_level": automation_level,
            "confidence": confidence,
            "status": status,
            "source_agent": source_agent,
            "created_at": now,
        }
        if resolved_at:
            data["resolved_at"] = resolved_at

        self.db.insert("approval_requests", data)
        return record_id

    def _get_approval_or_raise(self, approval_id: str) -> dict[str, Any]:
        record = self.db.get_by_id("approval_requests", approval_id)
        if not record:
            raise ResourceNotFound("ApprovalRequest", approval_id)
        return record


# ── Utility ──────────────────────────────────────────────────────────

_LEVEL_ORDER = {
    AutomationLevel.L1: 1,
    AutomationLevel.L2: 2,
    AutomationLevel.L3: 3,
    AutomationLevel.L4: 4,
}


def _level_rank(level: AutomationLevel) -> int:
    return _LEVEL_ORDER.get(level, 2)


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.now(timezone.utc)
