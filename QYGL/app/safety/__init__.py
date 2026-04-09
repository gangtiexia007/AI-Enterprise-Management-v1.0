"""Package 4: Safety Layer — Approval Gateway, Shadow Mode, Dispute Center.

All AI-initiated actions must pass through the ApprovalGateway before
producing side-effects.  Shadow mode intercepts actions for dry-run
analysis.  The DisputeCenter lets employees challenge AI decisions.
"""

from app.safety.approval import ApprovalGateway, ApprovalResult
from app.safety.dispute import DisputeCenter
from app.safety.shadow import ShadowModeService

__all__ = [
    "ApprovalGateway",
    "ApprovalResult",
    "DisputeCenter",
    "ShadowModeService",
]
