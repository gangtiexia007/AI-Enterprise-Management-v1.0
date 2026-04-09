"""Skill System — tool registration, execution, and discovery.

Public surface:
    - ``@tool`` decorator
    - ``ToolCall``, ``ToolResult``, ``ToolContext`` contracts
    - ``execute_tool`` for the agent loop
    - ``SkillRegistry`` for tool discovery
"""

from app.skills.sdk import (
    ToolCall,
    ToolContext,
    ToolDef,
    ToolResult,
    execute_tool,
    get_tool_registry,
    tool,
)
from app.skills.registry import SkillRegistry

__all__ = [
    "tool",
    "ToolCall",
    "ToolContext",
    "ToolDef",
    "ToolResult",
    "execute_tool",
    "get_tool_registry",
    "SkillRegistry",
]
