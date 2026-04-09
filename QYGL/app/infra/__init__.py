"""Infrastructure — cross-cutting concerns shared by all packages.

Public surface:
    - ``AuditWriter`` — non-blocking audit log writer
    - ``EventBus`` — async pub/sub
    - ``HookEngine`` — event→condition→action pipeline
    - ``MemoryDispatcher`` — 5-layer memory system
    - Permission helpers
"""

from app.infra.audit import AuditWriter
from app.infra.eventbus import EventBus
from app.infra.hooks import HookEngine
from app.infra.memory import MemoryDispatcher
from app.infra.permission import (
    check_dashboard_access,
    check_permission_level,
    check_tier,
    effective_permission,
    max_permission_for_tier,
    permission_middleware,
)

__all__ = [
    "AuditWriter",
    "EventBus",
    "HookEngine",
    "MemoryDispatcher",
    "check_tier",
    "check_permission_level",
    "check_dashboard_access",
    "effective_permission",
    "max_permission_for_tier",
    "permission_middleware",
]
