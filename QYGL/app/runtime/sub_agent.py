"""F10: Sub-Agent Runtime — 4 standard roles with permission-isolated AgentLoop instances.

Roles
-----
* **Director** — main agent; drives the conversation and may spawn sub-agents.
* **Analyst** — read-only (P0); analyses data, generates insights.
* **Coach** — advisory (P0); gives coaching suggestions, never executes.
* **Executor** — action role; P2 by default, P3+ requires approval gateway.

Constraints:
- Each sub-agent gets its own ``AgentLoop`` instance.
- sub-agent permissions ≤ parent (Director) permissions.
- Only the Director can call sub-agents (no sub-agent chains).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.database import Database
from app.core.enums import PermissionLevel, SubAgentRole
from app.core.exceptions import (
    InsufficientPermissionLevel,
    PermissionDenied,
    QFBJError,
    ResourceNotFound,
)
from app.core.models import AgentResponse, SubAgent, UnifiedMessage
from app.runtime.agent_loop import AgentLoop
from app.runtime.context import ContextManager
from app.runtime.llm import LLMClient
from app.runtime.model_router import ModelRouter

logger = logging.getLogger(__name__)

ROLE_MAX_PERMISSION: dict[str, int] = {
    SubAgentRole.DIRECTOR: PermissionLevel.P4,
    SubAgentRole.ANALYST: PermissionLevel.P0,
    SubAgentRole.COACH: PermissionLevel.P0,
    SubAgentRole.EXECUTOR: PermissionLevel.P2,
}


@dataclass
class SubAgentSpec:
    """Resolved specification for a sub-agent invocation."""

    name: str
    role: str
    system_prompt: str
    model: str
    max_permission: int
    skills: list[str]


class SubAgentRunner:
    """Manages sub-agent invocations from a Director agent.

    The runner enforces:
    - Permission ceiling: effective = min(parent, role cap, DB config)
    - Only one level of delegation (no sub-agent → sub-agent chains)
    """

    def __init__(
        self,
        db: Database | None = None,
        llm: LLMClient | None = None,
        model_router: ModelRouter | None = None,
    ):
        self._db = db or Database.get_instance()
        self._llm = llm or LLMClient()
        self._router = model_router or ModelRouter.get_instance(self._db)

    def list_sub_agents(self, team_id: str) -> list[dict[str, Any]]:
        """Return all configured sub-agents for a team."""
        rows = self._db.query(
            "sub_agents", {"team_id": team_id}, order_by="sort_order",
        )
        return rows

    def get_sub_agent(self, team_id: str, name: str) -> dict[str, Any]:
        """Look up a sub-agent by team + name."""
        rows = self._db.query(
            "sub_agents", {"team_id": team_id, "name": name}, limit=1,
        )
        if not rows:
            raise ResourceNotFound("SubAgent", f"{team_id}/{name}")
        return rows[0]

    async def invoke(
        self,
        *,
        team: dict[str, Any],
        sub_agent_name: str,
        user_content: str,
        parent_permission: int,
        employee: dict[str, Any] | None = None,
        conversation_id: str = "",
    ) -> AgentResponse:
        """Invoke a sub-agent and return its response.

        ``parent_permission`` is the Director's effective permission.
        The sub-agent's actual permission = min(parent, role cap, DB cap).
        """
        spec = self._resolve_spec(team, sub_agent_name, parent_permission)

        logger.info(
            "Invoking sub-agent '%s' (role=%s, perm=P%d, model=%s) for team %s",
            spec.name, spec.role, spec.max_permission, spec.model, team["id"],
        )

        ctx_mgr = ContextManager(self._db, self._llm)
        loop = AgentLoop(
            db=self._db, llm=self._llm,
            context_mgr=ctx_mgr, model_router=self._router,
        )

        sub_team = dict(team)
        if spec.system_prompt:
            sub_team["system_prompt"] = spec.system_prompt
        if spec.model:
            sub_team["primary_model"] = spec.model

        sub_employee = dict(employee) if employee else {}
        sub_employee["_sub_agent_permission"] = spec.max_permission

        message = UnifiedMessage(
            channel=team.get("channel", "dashboard"),
            sender_id=f"sub:{spec.name}",
            team_id=team["id"],
            employee_id=(employee or {}).get("id", ""),
            content=user_content,
        )

        response = await loop.run(
            message,
            team=sub_team,
            employee=sub_employee or None,
            conversation_id=conversation_id,
        )

        response.metadata["sub_agent"] = spec.name
        response.metadata["sub_agent_role"] = spec.role
        response.metadata["sub_agent_permission"] = spec.max_permission

        return response

    def _resolve_spec(
        self,
        team: dict[str, Any],
        sub_agent_name: str,
        parent_permission: int,
    ) -> SubAgentSpec:
        """Build a resolved ``SubAgentSpec`` with clamped permissions."""
        team_id = team["id"]
        row = self.get_sub_agent(team_id, sub_agent_name)

        role = row.get("role", SubAgentRole.EXECUTOR)
        role_cap = ROLE_MAX_PERMISSION.get(role, PermissionLevel.P0)
        db_cap = row.get("max_permission", 0)

        effective = min(parent_permission, role_cap, db_cap) if db_cap > 0 else min(parent_permission, role_cap)

        model_override = row.get("model_override", "")
        model = self._router.select_model_for_sub_agent(team_id, model_override)

        skills_raw = row.get("skills_json", "[]")
        if isinstance(skills_raw, str):
            try:
                import json
                skills = json.loads(skills_raw)
            except (json.JSONDecodeError, TypeError):
                skills = []
        else:
            skills = skills_raw

        return SubAgentSpec(
            name=row.get("name", sub_agent_name),
            role=role,
            system_prompt=row.get("system_prompt", ""),
            model=model,
            max_permission=effective,
            skills=skills,
        )

    # ── Convenience: pre-built role invocations ──────────────────

    async def invoke_analyst(
        self,
        team: dict[str, Any],
        query: str,
        parent_permission: int,
        employee: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Invoke the team's Analyst sub-agent for a read-only analysis."""
        analysts = self._find_by_role(team["id"], SubAgentRole.ANALYST)
        name = analysts[0]["name"] if analysts else "analyst"
        return await self.invoke(
            team=team, sub_agent_name=name,
            user_content=query, parent_permission=parent_permission,
            employee=employee,
        )

    async def invoke_coach(
        self,
        team: dict[str, Any],
        topic: str,
        parent_permission: int,
        employee: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Invoke the team's Coach sub-agent for advisory suggestions."""
        coaches = self._find_by_role(team["id"], SubAgentRole.COACH)
        name = coaches[0]["name"] if coaches else "coach"
        return await self.invoke(
            team=team, sub_agent_name=name,
            user_content=topic, parent_permission=parent_permission,
            employee=employee,
        )

    async def invoke_executor(
        self,
        team: dict[str, Any],
        instruction: str,
        parent_permission: int,
        employee: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Invoke the team's Executor sub-agent for an action task."""
        executors = self._find_by_role(team["id"], SubAgentRole.EXECUTOR)
        name = executors[0]["name"] if executors else "executor"
        return await self.invoke(
            team=team, sub_agent_name=name,
            user_content=instruction, parent_permission=parent_permission,
            employee=employee,
        )

    def _find_by_role(self, team_id: str, role: str) -> list[dict[str, Any]]:
        return self._db.query(
            "sub_agents", {"team_id": team_id, "role": role},
            order_by="sort_order", limit=5,
        )
