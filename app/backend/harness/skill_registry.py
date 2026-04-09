"""
SkillRegistry: unified registry for builtin, custom (SKILL.md), and MCP skills.

Each skill is stored as a SkillDefinition with:
- name, description, parameters schema (JSON Schema style)
- execute() callable
- permission_level (0=auto, 1=rule, 2=approval, 3=strong_approval, 4=forbidden)
"""
import json
import logging
import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional
from enum import IntEnum

logger = logging.getLogger(__name__)


class PermissionLevel(IntEnum):
    AUTO = 0
    RULE = 1
    APPROVAL = 2
    STRONG_APPROVAL = 3
    FORBIDDEN = 4


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None

    def to_str(self) -> str:
        if self.success:
            return json.dumps(self.data, ensure_ascii=False, default=str) if not isinstance(self.data, str) else self.data
        return f"Error: {self.error}"


@dataclass
class SkillDefinition:
    name: str
    description: str
    skill_type: str  # builtin / custom / mcp
    parameters: dict = field(default_factory=dict)
    permission_level: int = 0
    _execute: Optional[Callable[..., Awaitable[ToolResult]]] = field(default=None, repr=False)

    def to_openai_function(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}, "required": []},
            },
        }


_BUILTIN_REGISTRY: dict[str, SkillDefinition] = {}


def tool(
    name: str,
    description: str,
    parameters: Optional[dict] = None,
    permission_level: int = 0,
):
    """Decorator to register a builtin skill function."""
    def decorator(fn: Callable[..., Awaitable[ToolResult]]):
        skill = SkillDefinition(
            name=name,
            description=description,
            skill_type="builtin",
            parameters=parameters or {"type": "object", "properties": {}, "required": []},
            permission_level=permission_level,
            _execute=fn,
        )
        _BUILTIN_REGISTRY[name] = skill
        fn._skill_def = skill
        return fn
    return decorator


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}

    def auto_discover_builtins(self):
        """Import all modules in skills/builtin/ to trigger @tool decorators."""
        import harness.skills.builtin as pkg
        for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            try:
                importlib.import_module(f"harness.skills.builtin.{modname}")
            except Exception as e:
                logger.error(f"Failed to import builtin skill {modname}: {e}")
        for name, skill_def in _BUILTIN_REGISTRY.items():
            self._skills[name] = skill_def
        logger.info(f"Discovered {len(_BUILTIN_REGISTRY)} builtin skills")

    def register(self, skill_def: SkillDefinition):
        self._skills[skill_def.name] = skill_def

    def unregister(self, name: str):
        self._skills.pop(name, None)

    def register_custom_skill(self, name: str, description: str, content: str, permission_level: int = 0):
        """Register a SKILL.md prompt-based skill."""
        async def execute_custom(db_session=None, **kwargs) -> ToolResult:
            return ToolResult(success=True, data=f"[SKILL.md 内容]\n{content}\n\n请根据上述指南执行。用户参数: {json.dumps(kwargs, ensure_ascii=False)}")

        skill = SkillDefinition(
            name=name,
            description=description,
            skill_type="custom",
            parameters={"type": "object", "properties": {"instruction": {"type": "string", "description": "额外指令"}}, "required": []},
            permission_level=permission_level,
            _execute=execute_custom,
        )
        self._skills[name] = skill

    def register_mcp_skill(self, name: str, description: str, endpoint: str, auth_config: dict, permission_level: int = 0):
        """Register an MCP external tool."""
        from harness.mcp_client import mcp_client

        async def execute_mcp(db_session=None, **kwargs) -> ToolResult:
            return await mcp_client.call_tool(endpoint, name, kwargs, auth_config)

        skill = SkillDefinition(
            name=name,
            description=description,
            skill_type="mcp",
            parameters={"type": "object", "properties": {}, "required": []},
            permission_level=permission_level,
            _execute=execute_mcp,
        )
        self._skills[name] = skill

    def list_skills(self, skill_type: Optional[str] = None) -> list[SkillDefinition]:
        skills = list(self._skills.values())
        if skill_type:
            skills = [s for s in skills if s.skill_type == skill_type]
        return skills

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def get_tool_schemas(self, max_permission: int = 4) -> list[dict]:
        """Return OpenAI function-calling schemas for all eligible skills."""
        return [
            s.to_openai_function()
            for s in self._skills.values()
            if s.permission_level <= max_permission and s._execute is not None
        ]

    async def execute(self, skill_name: str, params: dict, db_session=None) -> ToolResult:
        skill = self._skills.get(skill_name)
        if not skill:
            return ToolResult(success=False, error=f"Skill '{skill_name}' not found")
        if skill._execute is None:
            return ToolResult(success=False, error=f"Skill '{skill_name}' has no executor")
        try:
            return await skill._execute(db_session=db_session, **params)
        except Exception as e:
            logger.error(f"Skill {skill_name} execution error: {e}")
            return ToolResult(success=False, error=str(e))


skill_registry = SkillRegistry()
