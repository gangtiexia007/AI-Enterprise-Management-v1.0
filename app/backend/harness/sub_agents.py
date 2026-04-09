"""
SubAgentManager: spawn, configure, and dispatch sub-agents.

Each sub-agent has:
- Its own model (can differ from main agent)
- Restricted tool set (allowed_tools whitelist)
- Read-only or read-write mode
- Independent system prompt
"""
import json
import logging
from typing import Optional
from harness.prompt_templates import build_system_prompt, ROLE_TEMPLATES

logger = logging.getLogger(__name__)

DEFAULT_SUB_AGENTS = [
    {
        "role": "director",
        "name": "管理总监",
        "description": "全局把控，帮老板做决策分析。重点：目标达成率、资源分配、团队效率、风险预警。",
        "read_only": 1,
        "can_spawn_children": 0,
        "allowed_tools": json.dumps(["today_tasks", "overdue_tasks", "team_progress", "daily_report", "data_summary", "list_goals", "kpi_summary"]),
        "permission_level": 4,
    },
    {
        "role": "analyst",
        "name": "数据分析师",
        "description": "数据挖掘和趋势分析。重点：KPI 趋势、任务完成率、员工绩效对比、异常检测。",
        "read_only": 1,
        "can_spawn_children": 0,
        "allowed_tools": json.dumps(["data_summary", "kpi_summary", "team_progress", "list_goals", "search_knowledge"]),
        "permission_level": 0,
    },
    {
        "role": "coach",
        "name": "管理教练",
        "description": "员工辅导和能力提升。重点：绩效短板分析、个性化建议、成长路径规划。",
        "read_only": 1,
        "can_spawn_children": 0,
        "allowed_tools": json.dumps(["kpi_summary", "search_knowledge", "data_summary"]),
        "permission_level": 0,
    },
    {
        "role": "executor",
        "name": "执行助手",
        "description": "具体任务的分解和跟踪。重点：任务拆解、时间规划、进度追踪、催办提醒。",
        "read_only": 0,
        "can_spawn_children": 0,
        "allowed_tools": json.dumps(["today_tasks", "overdue_tasks", "urge_overdue", "create_task", "team_progress"]),
        "permission_level": 2,
    },
]


class SubAgentManager:
    def select_role(self, user_input: str) -> str:
        msg = user_input.lower()
        if any(kw in msg for kw in ["目标", "战略", "规划", "决策", "分配"]):
            return "director"
        if any(kw in msg for kw in ["数据", "分析", "趋势", "对比", "统计", "报表"]):
            return "analyst"
        if any(kw in msg for kw in ["辅导", "培训", "成长", "建议", "改进", "短板"]):
            return "coach"
        if any(kw in msg for kw in ["任务", "拆解", "执行", "催办", "进度", "派发"]):
            return "executor"
        return "director"

    def get_system_prompt(self, role: str, custom_prompt: str = "") -> str:
        return build_system_prompt(role, custom_prompt)

    async def dispatch(self, sub_agent_config: dict, task: str, context: str, db_session=None) -> str:
        """
        Dispatch a task to a sub-agent. The sub-agent runs with its own model
        and restricted tool set, then returns a summary.
        """
        from harness.ai_client import ai_client
        from harness.skill_registry import skill_registry

        role = sub_agent_config.get("role", "director")
        model = sub_agent_config.get("model") or None
        custom_prompt = sub_agent_config.get("system_prompt", "")
        system_prompt = self.get_system_prompt(role, custom_prompt)

        allowed_tools_raw = sub_agent_config.get("allowed_tools", "[]")
        if isinstance(allowed_tools_raw, str):
            try:
                allowed_names = json.loads(allowed_tools_raw)
            except json.JSONDecodeError:
                allowed_names = []
        else:
            allowed_names = allowed_tools_raw

        all_schemas = skill_registry.get_tool_schemas()
        filtered_schemas = [s for s in all_schemas if s["function"]["name"] in allowed_names] if allowed_names else []

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.append({"role": "system", "content": f"当前数据:\n{context}"})
        messages.append({"role": "user", "content": task})

        if filtered_schemas:
            response = await ai_client.chat_with_tools(messages=messages, tools=filtered_schemas, model=model)
            if response.get("type") == "tool_calls":
                for tc in response["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                    if fn_name in allowed_names:
                        result = await skill_registry.execute(fn_name, fn_args, db_session=db_session)
                        messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result.to_str()})

                final = await ai_client.chat_with_tools(messages=messages, model=model)
                return final.get("content", "子Agent 未返回结果")
            return response.get("content", "")
        else:
            result = await ai_client.chat(messages, model=model)
            return result

    def get_default_configs(self) -> list[dict]:
        return DEFAULT_SUB_AGENTS

    def ensure_defaults_in_db(self, db_session):
        """Create default sub-agents in DB if none exist."""
        from models import SubAgentModel
        count = db_session.query(SubAgentModel).count()
        if count > 0:
            return
        for cfg in DEFAULT_SUB_AGENTS:
            sa = SubAgentModel(
                role=cfg["role"],
                name=cfg["name"],
                description=cfg["description"],
                read_only=cfg["read_only"],
                can_spawn_children=cfg["can_spawn_children"],
                allowed_tools=cfg["allowed_tools"],
            )
            db_session.add(sa)
        db_session.commit()
        logger.info(f"Created {len(DEFAULT_SUB_AGENTS)} default sub-agents")


sub_agent_manager = SubAgentManager()
