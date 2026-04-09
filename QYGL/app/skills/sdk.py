"""F12: Skill SDK — @tool decorator, ToolCall / ToolResult contracts, permission gate.

Every function exposed to the agent runtime MUST be decorated with @tool.
The decorator enforces permission checks (P0–P4) and writes an audit trail.
Tool naming convention: {skill_name}__{function_name} (double underscore).
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.core.enums import PermissionLevel
from app.core.exceptions import InsufficientPermissionLevel, ToolCallFailed

logger = logging.getLogger(__name__)

# ── Contracts ─────────────────────────────────────────────────────────


@dataclass
class ToolContext:
    """Ambient context injected into every tool call by the agent loop."""

    team_id: str = ""
    employee_id: str = ""
    user_tier: str = "T3"
    caller_permission: int = 0
    actor: str = ""
    department: str = ""
    conversation_id: str = ""


@dataclass
class ToolCall:
    """Inbound request to invoke a tool."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])


@dataclass
class ToolResult:
    """Outbound result after a tool executes."""

    call_id: str
    tool_name: str
    success: bool
    data: Any = None
    error: str = ""
    elapsed_ms: float = 0.0


@dataclass
class ToolDef:
    """Internal registration record for a single tool function."""

    name: str
    func: Callable[..., Any]
    raw_func: Callable[..., Any]
    permission: PermissionLevel
    description: str
    skill_name: str


# ── Global Registry (populated by @tool) ──────────────────────────────

_TOOL_REGISTRY: dict[str, ToolDef] = {}


def get_tool_registry() -> dict[str, ToolDef]:
    return _TOOL_REGISTRY


# ── @tool Decorator ───────────────────────────────────────────────────


def tool(
    *,
    permission: PermissionLevel = PermissionLevel.P0,
    description: str = "",
    name_override: str = "",
):
    """Register a function as a callable tool.

    The tool name defaults to ``{module_leaf}__{func_name}`` unless
    *name_override* is given.
    """

    def decorator(func: Callable) -> Callable:
        module_path = func.__module__ or ""
        skill_name = module_path.rsplit(".", 1)[-1] if module_path else "unknown"
        tool_name = name_override or f"{skill_name}__{func.__name__}"

        @functools.wraps(func)
        async def wrapper(ctx: ToolContext, **kwargs: Any) -> ToolResult:
            if ctx.caller_permission < permission.value:
                raise InsufficientPermissionLevel(permission.value, ctx.caller_permission)

            t0 = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(func):
                    result_data = await func(ctx, **kwargs)
                else:
                    result_data = func(ctx, **kwargs)
                elapsed = (time.monotonic() - t0) * 1000
                result = ToolResult(
                    call_id="",
                    tool_name=tool_name,
                    success=True,
                    data=result_data,
                    elapsed_ms=round(elapsed, 2),
                )
                _schedule_audit(ctx, tool_name, kwargs, result)
                return result
            except InsufficientPermissionLevel:
                raise
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000
                result = ToolResult(
                    call_id="",
                    tool_name=tool_name,
                    success=False,
                    error=str(exc),
                    elapsed_ms=round(elapsed, 2),
                )
                _schedule_audit(ctx, tool_name, kwargs, result)
                raise ToolCallFailed(tool_name, str(exc)) from exc

        wrapper._tool_name = tool_name  # type: ignore[attr-defined]
        wrapper._tool_permission = permission  # type: ignore[attr-defined]

        _TOOL_REGISTRY[tool_name] = ToolDef(
            name=tool_name,
            func=wrapper,
            raw_func=func,
            permission=permission,
            description=description or inspect.getdoc(func) or "",
            skill_name=skill_name,
        )
        return wrapper

    return decorator


# ── Tool Execution ────────────────────────────────────────────────────


async def execute_tool(call: ToolCall, ctx: ToolContext) -> ToolResult:
    """Look up a tool by name and execute it with the given context."""

    tool_def = _TOOL_REGISTRY.get(call.tool_name)
    if tool_def is None:
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            success=False,
            error=f"Tool '{call.tool_name}' not found",
        )
    try:
        result = await tool_def.func(ctx, **call.arguments)
        result.call_id = call.call_id
        return result
    except InsufficientPermissionLevel as exc:
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            success=False,
            error=str(exc),
        )
    except ToolCallFailed as exc:
        return ToolResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            success=False,
            error=exc.message,
        )


# ── Audit Plumbing ───────────────────────────────────────────────────

_audit_sink: Callable[..., None] | None = None


def set_audit_sink(sink: Callable[..., None]) -> None:
    """Called once at startup by infra.audit to wire up the audit writer."""
    global _audit_sink
    _audit_sink = sink


def _schedule_audit(
    ctx: ToolContext,
    tool_name: str,
    kwargs: dict[str, Any],
    result: ToolResult,
) -> None:
    if _audit_sink is None:
        return
    try:
        _audit_sink(
            actor=ctx.actor or ctx.employee_id or "system",
            team_id=ctx.team_id,
            action=f"tool_call:{tool_name}",
            resource_type="tool",
            resource_id=tool_name,
            details_json={
                "arguments": _safe_serialize(kwargs),
                "success": result.success,
                "error": result.error,
                "elapsed_ms": result.elapsed_ms,
            },
        )
    except Exception:
        logger.debug("Audit write failed for %s", tool_name, exc_info=True)


def _safe_serialize(obj: Any, max_len: int = 500) -> Any:
    """Truncate large values so audit payloads stay manageable."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v, max_len) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        preview = [_safe_serialize(i, max_len) for i in obj[:20]]
        if len(obj) > 20:
            preview.append(f"... ({len(obj)} items)")
        return preview
    s = str(obj)
    return s[:max_len] + "..." if len(s) > max_len else s
