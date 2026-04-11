"""
PermissionGateway: enforce permission tiers for skill execution.

P0 (AUTO)            - Read data, query stats — always allowed
P1 (RULE)            - Send notifications, generate reports — rule-gated
P2 (APPROVAL)        - Create/modify tasks, update KPI — needs approval for batch
P3 (STRONG_APPROVAL) - Bulk operations, delete data — requires explicit confirmation
P4 (FORBIDDEN)       - System config changes — blocked at agent level
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PermissionGateway:
    def __init__(self):
        self._overrides: dict[str, bool] = {}

    def check(self, skill_name: str, db_session=None) -> bool | str:
        """Check if a skill is allowed to execute. Returns True, False, or 'pending_approval'."""
        if skill_name in self._overrides:
            return self._overrides[skill_name]

        from harness.skill_registry import skill_registry
        skill = skill_registry.get_skill(skill_name)
        if not skill:
            return False

        if skill.permission_level <= 2:
            return True

        if skill.permission_level == 3:
            logger.warning(f"Skill '{skill_name}' requires strong approval (P3)")
            return "pending_approval"

        if skill.permission_level >= 4:
            logger.warning(f"Skill '{skill_name}' is forbidden (P4)")
            return False

        return True

    def allow(self, skill_name: str):
        self._overrides[skill_name] = True

    def deny(self, skill_name: str):
        self._overrides[skill_name] = False

    def clear_override(self, skill_name: str):
        self._overrides.pop(skill_name, None)

    def get_level_for_skill(self, skill_name: str) -> int:
        from harness.skill_registry import skill_registry
        skill = skill_registry.get_skill(skill_name)
        return skill.permission_level if skill else -1


permission_gateway = PermissionGateway()
