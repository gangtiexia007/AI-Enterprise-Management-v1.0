"""F02: Team Registry — CRUD + configuration loading for Agent Teams (APP layer).

Teams are lightweight config shells. They declare what OS services they need
but never implement business logic.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import AutomationProfile, TeamStatus
from app.core.exceptions import TeamNotFound, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_ESCALATION = {"intervals_minutes": [30, 60, 120], "levels": ["employee", "manager", "boss"]}

AUTOMATION_PRESETS: dict[str, dict[str, Any]] = {
    AutomationProfile.STARTUP: {
        "default_automation": "L1",
        "shadow_duration_days": 14,
        "escalation_frequency": "relaxed",
        "kpi_template": "simplified",
    },
    AutomationProfile.MID_MANAGER: {
        "default_automation": "L2",
        "shadow_duration_days": 7,
        "escalation_frequency": "standard",
        "kpi_template": "standard",
    },
    AutomationProfile.PROCESS_DRIVEN: {
        "default_automation": "L3",
        "shadow_duration_days": 7,
        "escalation_frequency": "strict",
        "kpi_template": "full",
    },
}


class TeamRegistry:

    def __init__(self, db: Database | None = None):
        self.db = db or Database.get_instance()

    def create_team(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data.get("name"):
            raise ValidationError("Team name is required")

        existing = self.db.query("teams", {"name": data["name"]}, limit=1)
        if existing:
            raise ValidationError(f"Team name '{data['name']}' already exists")

        team_id = data.get("id") or new_id()
        profile = data.get("automation_profile", AutomationProfile.STARTUP.value)

        record = {
            "id": team_id,
            "name": data["name"],
            "display_name": data.get("display_name", data["name"]),
            "tier": data.get("tier", "T2"),
            "status": TeamStatus.DRAFT.value,
            "department": data.get("department", ""),
            "system_prompt": data.get("system_prompt", ""),
            "primary_model": data.get("primary_model", ""),
            "fallback_model": data.get("fallback_model", ""),
            "data_scope_json": json.dumps(data.get("data_scope_json", {}), ensure_ascii=False),
            "knowledge_scope_json": json.dumps(data.get("knowledge_scope_json", {}), ensure_ascii=False),
            "escalation_json": json.dumps(data.get("escalation_json", DEFAULT_ESCALATION), ensure_ascii=False),
            "automation_profile": profile,
        }
        self.db.insert("teams", record)

        self._init_shadow_config(team_id, profile)
        logger.info("Team created: %s (%s)", team_id, data["name"])
        return self.get_team(team_id)

    def get_team(self, team_id: str) -> dict[str, Any]:
        row = self.db.get_by_id("teams", team_id)
        if not row:
            raise TeamNotFound(team_id)
        return self._parse_json_fields(row)

    def get_team_config(self, team_id: str) -> dict[str, Any]:
        team = self.get_team(team_id)
        team["bots"] = self.db.query("team_bots", {"team_id": team_id})
        team["sub_agents"] = self.db.query("sub_agents", {"team_id": team_id}, order_by="sort_order")
        team["skills"] = self.db.query("team_skills", {"team_id": team_id})
        team["kpi_definitions"] = self.db.query("kpi_definitions", {"team_id": team_id})
        team["shadow_config"] = self.db.query("team_shadow_config", {"team_id": team_id}, limit=1)
        team["shadow_config"] = team["shadow_config"][0] if team["shadow_config"] else None
        team["employees"] = self.db.query("employees", {"team_id": team_id})
        return team

    def update_team(self, team_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self.get_team(team_id)  # ensure exists
        for field in ("data_scope_json", "knowledge_scope_json", "escalation_json"):
            if field in data and isinstance(data[field], (dict, list)):
                data[field] = json.dumps(data[field], ensure_ascii=False)
        self.db.update("teams", team_id, data)
        logger.info("Team updated: %s", team_id)
        return self.get_team(team_id)

    def list_teams(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = self.db.query("teams", filters, order_by="created_at DESC")
        return [self._parse_json_fields(r) for r in rows]

    def delete_team(self, team_id: str) -> None:
        employees = self.db.count("employees", {"team_id": team_id})
        if employees > 0:
            raise ValidationError(
                f"Cannot delete team {team_id}: {employees} employees still assigned. Transfer them first."
            )
        self.db.execute("DELETE FROM team_shadow_config WHERE team_id=?", (team_id,))
        self.db.execute("DELETE FROM team_bots WHERE team_id=?", (team_id,))
        self.db.execute("DELETE FROM sub_agents WHERE team_id=?", (team_id,))
        self.db.execute("DELETE FROM team_skills WHERE team_id=?", (team_id,))
        self.db.delete("teams", team_id)
        logger.info("Team deleted: %s", team_id)

    def create_boss_agent(self, company_name: str = "", system_prompt: str = "") -> dict[str, Any]:
        """Create the Boss Agent — a special team that serves the boss directly.
        
        The Boss Agent has data_scope='*' (can read all teams) and is_boss_agent=1.
        Only one Boss Agent should exist. If one already exists, return it.
        """
        existing = self.db.query("teams", {"is_boss_agent": 1}, limit=1)
        if existing:
            return self._parse_json_fields(existing[0])

        default_prompt = f"""你是{company_name or '本公司'}的AI管理总助（Boss Agent）。

你的职责：
- 帮助老板掌控公司全局运营状况
- 汇报各团队的 KPI、任务完成情况、异常事件
- 处理老板发来的文件（Excel/CSV），自动解析并整理数据
- 回答老板关于业绩、人员、运营的任何问题
- 当老板下达指令时，将任务分发到对应的 Agent 团队

你可以查看所有团队的数据，不受数据范围限制。"""

        team_id = new_id()
        record = {
            "id": team_id,
            "name": "boss_agent",
            "display_name": "Boss Agent（老板助手）",
            "tier": "T1",
            "status": "active",
            "department": "",
            "system_prompt": system_prompt or default_prompt,
            "primary_model": "",
            "fallback_model": "",
            "data_scope_json": json.dumps({"scope": "*"}),
            "knowledge_scope_json": json.dumps({}),
            "escalation_json": json.dumps({"intervals_minutes": [15, 30, 60], "levels": ["boss"]}),
            "automation_profile": "startup",
            "is_boss_agent": 1,
        }
        self.db.insert("teams", record)
        logger.info("Boss Agent created: %s", team_id)
        return self.get_team(team_id)

    # ── Helpers ──────────────────────────────────────────────────

    def _init_shadow_config(self, team_id: str, profile: str) -> None:
        preset = AUTOMATION_PRESETS.get(profile, AUTOMATION_PRESETS[AutomationProfile.STARTUP])
        self.db.insert("team_shadow_config", {
            "id": new_id(),
            "team_id": team_id,
            "mode": "shadow",
            "shadow_duration_days": preset["shadow_duration_days"],
        })

    @staticmethod
    def _parse_json_fields(row: dict[str, Any]) -> dict[str, Any]:
        for field in ("data_scope_json", "knowledge_scope_json", "escalation_json"):
            if field in row and isinstance(row[field], str):
                try:
                    row[field] = json.loads(row[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row
