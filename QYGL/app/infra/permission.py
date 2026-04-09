"""F28: Permission — T1/T2/T3 tier checks + P0–P4 operation-level enforcement.

Provides both programmatic helpers and a FastAPI middleware function
for request-level permission validation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.enums import PermissionLevel, UserTier
from app.core.exceptions import InsufficientPermissionLevel, PermissionDenied

logger = logging.getLogger(__name__)

# ── Tier → Maximum Operation Level Mapping ────────────────────────────

_TIER_MAX_PERMISSION: dict[str, int] = {
    UserTier.T1: PermissionLevel.P4,
    UserTier.T2: PermissionLevel.P3,
    UserTier.T3: PermissionLevel.P1,
}

# ── Tier → Allowed Dashboard Sections ────────────────────────────────

_TIER_DASHBOARD_ACCESS: dict[str, set[str]] = {
    UserTier.T1: {
        "overview", "teams", "employees", "tasks", "kpi", "goals",
        "approvals", "reports", "knowledge", "models", "skills",
        "settings", "audit", "disputes", "rewards", "customers",
        "hiring", "shadow",
    },
    UserTier.T2: {
        "overview", "teams", "employees", "tasks", "kpi", "goals",
        "approvals", "reports", "knowledge", "disputes", "rewards",
        "customers",
    },
    UserTier.T3: set(),
}


def max_permission_for_tier(tier: str) -> int:
    """Return the ceiling P-level for a user tier."""
    return _TIER_MAX_PERMISSION.get(tier, PermissionLevel.P0)


def check_tier(user_tier: str, required_tier: str) -> None:
    """Raise ``PermissionDenied`` if the user tier is lower than required.

    Tier ordering: T1 > T2 > T3.
    """
    tier_rank = {UserTier.T1: 3, UserTier.T2: 2, UserTier.T3: 1}
    user_rank = tier_rank.get(user_tier, 0)
    required_rank = tier_rank.get(required_tier, 99)
    if user_rank < required_rank:
        raise PermissionDenied(
            f"Requires tier {required_tier} or above, caller is {user_tier}",
        )


def check_permission_level(caller_level: int, required_level: int) -> None:
    """Raise ``InsufficientPermissionLevel`` when caller < required."""
    if caller_level < required_level:
        raise InsufficientPermissionLevel(required_level, caller_level)


def check_dashboard_access(user_tier: str, section: str) -> None:
    """Raise ``PermissionDenied`` if the tier cannot access *section*."""
    allowed = _TIER_DASHBOARD_ACCESS.get(user_tier, set())
    if section not in allowed:
        raise PermissionDenied(
            f"Tier {user_tier} cannot access dashboard section '{section}'",
        )


def effective_permission(user_tier: str, sub_agent_max: int) -> int:
    """Return the effective permission = min(tier ceiling, sub-agent cap)."""
    tier_max = max_permission_for_tier(user_tier)
    return min(tier_max, sub_agent_max)


def can_write(user_tier: str, caller_permission: int) -> bool:
    """Quick boolean check — needs at least P2."""
    return caller_permission >= PermissionLevel.P2


def requires_confirmation(permission_level: int) -> bool:
    """P3 requires dashboard confirmation."""
    return permission_level == PermissionLevel.P3


def requires_approval(permission_level: int) -> bool:
    """P4 requires approval gateway."""
    return permission_level >= PermissionLevel.P4


# ── FastAPI Middleware ────────────────────────────────────────────────


def permission_middleware(required_tier: str = UserTier.T2, section: str = ""):
    """Return a FastAPI dependency that enforces tier + dashboard section.

    Usage::

        @router.get("/teams", dependencies=[Depends(permission_middleware("T2", "teams"))])
        async def list_teams(): ...
    """
    from fastapi import Depends, HTTPException, Request

    async def _check(request: Request) -> None:
        user: dict[str, Any] = getattr(request.state, "user", {})
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user_tier = user.get("tier", UserTier.T3)
        try:
            check_tier(user_tier, required_tier)
            if section:
                check_dashboard_access(user_tier, section)
        except PermissionDenied as exc:
            raise HTTPException(status_code=403, detail=exc.message) from exc

    return Depends(_check)
