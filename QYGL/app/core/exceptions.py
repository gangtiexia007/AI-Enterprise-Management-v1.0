"""Global exception hierarchy.

All custom exceptions inherit from QFBJError so callers can catch broadly.
"""


class QFBJError(Exception):
    """Base exception for the entire system."""

    def __init__(self, message: str = "", code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(self.message)


# ── Permission ───────────────────────────────────────────────────────

class PermissionDenied(QFBJError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code="PERMISSION_DENIED")


class InsufficientPermissionLevel(PermissionDenied):
    def __init__(self, required: int, actual: int):
        super().__init__(
            f"Requires P{required}, caller has P{actual}",
        )
        self.code = "INSUFFICIENT_PERMISSION"


# ── Resource Not Found ───────────────────────────────────────────────

class ResourceNotFound(QFBJError):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type} '{resource_id}' not found",
            code="NOT_FOUND",
        )


class TeamNotFound(ResourceNotFound):
    def __init__(self, team_id: str):
        super().__init__("Team", team_id)


class EmployeeNotFound(ResourceNotFound):
    def __init__(self, identifier: str):
        super().__init__("Employee", identifier)


class SkillNotFound(ResourceNotFound):
    def __init__(self, skill_name: str):
        super().__init__("Skill", skill_name)


class ModelNotFound(ResourceNotFound):
    def __init__(self, model_id: str):
        super().__init__("Model", model_id)


# ── Budget ───────────────────────────────────────────────────────────

class BudgetExceeded(QFBJError):
    def __init__(self, model_id: str, limit_type: str):
        super().__init__(
            f"Token budget exceeded for model '{model_id}' ({limit_type})",
            code="BUDGET_EXCEEDED",
        )


# ── Validation ───────────────────────────────────────────────────────

class ValidationError(QFBJError):
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")


class StateTransitionError(QFBJError):
    def __init__(self, entity: str, current_state: str, target_state: str):
        super().__init__(
            f"Invalid state transition for {entity}: {current_state} → {target_state}",
            code="INVALID_STATE_TRANSITION",
        )


# ── Agent Runtime ────────────────────────────────────────────────────

class AgentLoopMaxTurns(QFBJError):
    def __init__(self, team_id: str, turns: int):
        super().__init__(
            f"Agent loop for team '{team_id}' hit max turns ({turns})",
            code="MAX_TURNS_REACHED",
        )


class ToolCallFailed(QFBJError):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(
            f"Tool call '{tool_name}' failed: {reason}",
            code="TOOL_CALL_FAILED",
        )


# ── Safety ───────────────────────────────────────────────────────────

class ApprovalRequired(QFBJError):
    def __init__(self, action_type: str):
        super().__init__(
            f"Action '{action_type}' requires approval",
            code="APPROVAL_REQUIRED",
        )


class ShadowModeActive(QFBJError):
    """Not a real error — used as a signal that an action was shadow-recorded."""

    def __init__(self, team_id: str):
        super().__init__(
            f"Team '{team_id}' is in shadow mode. Action recorded but not executed.",
            code="SHADOW_MODE",
        )


# ── Channel / IM ─────────────────────────────────────────────────────

class ChannelConnectionFailed(QFBJError):
    def __init__(self, channel: str, reason: str):
        super().__init__(
            f"Failed to connect {channel}: {reason}",
            code="CHANNEL_CONNECTION_FAILED",
        )


class BotCredentialInvalid(QFBJError):
    def __init__(self, channel: str, team_id: str):
        super().__init__(
            f"Invalid bot credentials for {channel} in team '{team_id}'",
            code="BOT_CREDENTIAL_INVALID",
        )


# ── Database ─────────────────────────────────────────────────────────

class DatabaseError(QFBJError):
    def __init__(self, message: str):
        super().__init__(message, code="DATABASE_ERROR")


class MigrationError(DatabaseError):
    def __init__(self, version: str, reason: str):
        super().__init__(f"Migration {version} failed: {reason}")
        self.code = "MIGRATION_ERROR"
