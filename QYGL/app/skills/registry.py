"""F16: Unified Skill Registry — builtin + custom (SKILL.md) + MCP sources.

The registry is the single place to discover what tools a team/sub-agent may
call.  It merges three sources:

* **builtin** — Python functions decorated with ``@tool``
* **custom** — parsed from ``SKILL.md`` files (prompt-based)
* **MCP** — imported from external MCP servers

Global skills (``is_global=True``) are available to every team.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from app.core.database import Database
from app.core.enums import SkillSource
from app.core.exceptions import SkillNotFound
from app.core.models import Skill, TeamSkill
from app.skills.sdk import ToolDef, get_tool_registry

logger = logging.getLogger(__name__)

def _params_from_func(func) -> dict:
    """Generate JSON Schema parameters from function signature."""
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return {"type": "object", "properties": {}}

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name == "ctx":
            continue

        ann = param.annotation
        prop: dict = {}

        if ann == str or ann == inspect.Parameter.empty:
            prop["type"] = "string"
        elif ann == int:
            prop["type"] = "integer"
        elif ann == float:
            prop["type"] = "number"
        elif ann == bool:
            prop["type"] = "boolean"
        elif ann == dict or str(ann).startswith("dict"):
            prop["type"] = "object"
        elif ann == list or str(ann).startswith("list"):
            prop["type"] = "array"
        else:
            prop["type"] = "string"

        if param.default == inspect.Parameter.empty:
            required.append(name)
        elif param.default is not None:
            prop["default"] = param.default

        properties[name] = prop

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class SkillRegistry:
    """Central registry that answers: *What tools can this team use?*"""

    _instance: SkillRegistry | None = None

    def __init__(self, db: Database | None = None):
        self._db = db or Database.get_instance()
        self._skills: dict[str, Skill] = {}
        self._tool_index: dict[str, list[str]] = {}

    @classmethod
    def get_instance(cls, db: Database | None = None) -> SkillRegistry:
        if cls._instance is None:
            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Registration ──────────────────────────────────────────────

    def register_skill(self, skill: Skill) -> None:
        """Add or update a skill in the in-memory index."""
        self._skills[skill.id] = skill
        tool_names = [t.get("name", "") for t in skill.tools_json if t.get("name")]
        self._tool_index[skill.id] = tool_names
        logger.info("Skill registered: %s (%s) — %d tools", skill.name, skill.source, len(tool_names))

    def register_builtin_skills(self) -> None:
        """Scan the ``@tool`` registry and create Skill records for each
        unique ``skill_name`` that isn't already persisted."""
        import app.skills.builtin  # noqa: F401 — triggers @tool registration
        tool_reg = get_tool_registry()
        skills_map: dict[str, list[ToolDef]] = {}
        for td in tool_reg.values():
            skills_map.setdefault(td.skill_name, []).append(td)

        from app.core.database import new_id

        for skill_name, tools in skills_map.items():
            existing = self._db.query("skills", {"name": skill_name, "source": SkillSource.BUILTIN}, limit=1)
            if existing:
                skill_id = existing[0]["id"]
            else:
                skill_id = new_id()
                self._db.insert("skills", {
                    "id": skill_id,
                    "name": skill_name,
                    "display_name": skill_name.replace("_", " ").title(),
                    "source": SkillSource.BUILTIN,
                    "is_global": True,
                    "tools_json": [
                        {"name": t.name, "description": t.description, "permission": t.permission.value}
                        for t in tools
                    ],
                })

            skill_row = self._db.get_by_id("skills", skill_id)
            if skill_row:
                self.register_skill(Skill(**self._parse_row(skill_row)))

    def register_custom_skill(
        self,
        name: str,
        display_name: str,
        description: str,
        tools_json: list[dict[str, Any]],
        config_json: dict[str, Any] | None = None,
        is_global: bool = False,
    ) -> Skill:
        """Register a custom (SKILL.md-parsed) skill."""
        from app.core.database import new_id

        existing = self._db.query("skills", {"name": name, "source": SkillSource.CUSTOM}, limit=1)
        if existing:
            skill_id = existing[0]["id"]
            self._db.update("skills", skill_id, {
                "display_name": display_name,
                "description": description,
                "tools_json": tools_json,
                "config_json": config_json or {},
            })
        else:
            skill_id = new_id()
            self._db.insert("skills", {
                "id": skill_id,
                "name": name,
                "display_name": display_name,
                "description": description,
                "source": SkillSource.CUSTOM,
                "tools_json": tools_json,
                "config_json": config_json or {},
                "is_global": is_global,
            })

        row = self._db.get_by_id("skills", skill_id)
        skill = Skill(**self._parse_row(row))
        self.register_skill(skill)
        return skill

    def register_mcp_skill(
        self,
        name: str,
        display_name: str,
        tools_json: list[dict[str, Any]],
        config_json: dict[str, Any] | None = None,
    ) -> Skill:
        """Register a skill imported from an MCP server."""
        from app.core.database import new_id

        existing = self._db.query("skills", {"name": name, "source": SkillSource.MCP}, limit=1)
        if existing:
            skill_id = existing[0]["id"]
            self._db.update("skills", skill_id, {
                "display_name": display_name,
                "tools_json": tools_json,
                "config_json": config_json or {},
            })
        else:
            skill_id = new_id()
            self._db.insert("skills", {
                "id": skill_id,
                "name": name,
                "display_name": display_name,
                "source": SkillSource.MCP,
                "tools_json": tools_json,
                "config_json": config_json or {},
                "is_global": False,
            })

        row = self._db.get_by_id("skills", skill_id)
        skill = Skill(**self._parse_row(row))
        self.register_skill(skill)
        return skill

    # ── Query ─────────────────────────────────────────────────────

    def get_skill(self, skill_id: str) -> Skill:
        if skill_id in self._skills:
            return self._skills[skill_id]
        row = self._db.get_by_id("skills", skill_id)
        if not row:
            raise SkillNotFound(skill_id)
        skill = Skill(**self._parse_row(row))
        self._skills[skill_id] = skill
        return skill

    def get_skill_by_name(self, name: str) -> Skill | None:
        for s in self._skills.values():
            if s.name == name:
                return s
        rows = self._db.query("skills", {"name": name}, limit=1)
        if rows:
            skill = Skill(**self._parse_row(rows[0]))
            self._skills[skill.id] = skill
            return skill
        return None

    def list_skills(self, source: str | None = None) -> list[Skill]:
        conditions: dict[str, Any] | None = {"source": source} if source else None
        rows = self._db.query("skills", conditions, order_by="name", limit=500)
        return [Skill(**self._parse_row(r)) for r in rows]

    def get_tools_for_team(
        self,
        team_id: str,
        sub_agent_name: str = "",
    ) -> list[ToolDef]:
        """Return the concrete ``ToolDef`` objects available to a team.

        Includes global skills + team-assigned skills.
        Optionally filters to a specific sub-agent assignment.
        """
        tool_reg = get_tool_registry()

        global_rows = self._db.query("skills", {"is_global": True}, limit=500)
        global_skill_ids = {r["id"] for r in global_rows}

        conditions: dict[str, Any] = {"team_id": team_id}
        if sub_agent_name:
            conditions["assigned_to"] = sub_agent_name
        ts_rows = self._db.query("team_skills", conditions, limit=500)
        team_skill_ids = {r["skill_id"] for r in ts_rows}

        all_skill_ids = global_skill_ids | team_skill_ids
        result: list[ToolDef] = []

        for sid in all_skill_ids:
            tool_names = self._tool_index.get(sid, [])
            for tn in tool_names:
                if tn in tool_reg:
                    result.append(tool_reg[tn])

        return result

    def get_tool_schemas_for_team(
        self,
        team_id: str,
        sub_agent_name: str = "",
    ) -> list[dict[str, Any]]:
        """Return OpenAI-function-style schemas for the team's tools."""
        defs = self.get_tools_for_team(team_id, sub_agent_name)
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": _params_from_func(td.raw_func),
                },
            }
            for td in defs
        ]

        global_rows = self._db.query("skills", {"is_global": True, "source": SkillSource.MCP}, limit=100)
        conditions: dict[str, Any] = {"team_id": team_id}
        if sub_agent_name:
            conditions["assigned_to"] = sub_agent_name
        ts_rows = self._db.query("team_skills", conditions, limit=500)
        team_skill_ids = {r["skill_id"] for r in ts_rows}

        mcp_skill_ids = {r["id"] for r in global_rows} | team_skill_ids
        for sid in mcp_skill_ids:
            row = self._db.get_by_id("skills", sid)
            if row:
                parsed = self._parse_row(row)
                if parsed.get("source") == SkillSource.MCP:
                    for tool_info in (parsed.get("tools_json") or []):
                        schemas.append({
                            "type": "function",
                            "function": {
                                "name": tool_info.get("name", ""),
                                "description": tool_info.get("description", ""),
                                "parameters": tool_info.get("parameters", {}),
                            },
                        })
        return schemas

    def assign_skill_to_team(
        self,
        team_id: str,
        skill_id: str,
        assigned_to: str = "main",
    ) -> None:
        """Create a ``team_skills`` record."""
        from app.core.database import new_id

        existing = self._db.query("team_skills", {
            "team_id": team_id,
            "skill_id": skill_id,
            "assigned_to": assigned_to,
        }, limit=1)
        if existing:
            return
        self._db.insert("team_skills", {
            "id": new_id(),
            "team_id": team_id,
            "skill_id": skill_id,
            "assigned_to": assigned_to,
        })

    # ── Internal ──────────────────────────────────────────────────

    @staticmethod
    def _parse_row(row: dict[str, Any]) -> dict[str, Any]:
        import json
        for field in ("tools_json", "config_json"):
            if field in row and isinstance(row[field], str):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    row[field] = [] if field == "tools_json" else {}
        if "is_global" in row:
            row["is_global"] = bool(row["is_global"])
        return row
