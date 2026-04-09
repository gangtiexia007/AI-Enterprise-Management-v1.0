"""
AgentLoop: full state-machine with Tool Use (function calling) and SubAgent dispatch.

States: INIT -> PLANNING -> TOOL_USE -> OBSERVATION -> SUB_AGENT -> RESPONSE -> MEMORY_UPDATE -> DONE
"""
import json
import enum
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 8


class AgentState(str, enum.Enum):
    INIT = "init"
    PLANNING = "planning"
    TOOL_USE = "tool_use"
    OBSERVATION = "observation"
    SUB_AGENT = "sub_agent"
    RESPONSE = "response"
    MEMORY_UPDATE = "memory_update"
    DONE = "done"
    ERROR = "error"


class AgentLoop:
    def __init__(self):
        self.state = AgentState.INIT
        self._iterations = 0

    def _transition(self, new_state: AgentState):
        logger.debug(f"AgentLoop: {self.state} -> {new_state}")
        self.state = new_state

    async def run(self, user_message: str, db_session, agent_mode: str = "full") -> str:
        """
        Main entry point. Runs the agent loop for a single user message.
        Returns the final assistant response text.
        """
        self._transition(AgentState.INIT)
        self._iterations = 0

        try:
            from harness.ai_client import ai_client
            from harness.skill_registry import skill_registry
            from harness.prompt_templates import build_system_prompt, build_context_message
            from harness.context_manager import ContextManager
            from harness.memory_manager import memory_manager
            from harness.permissions import permission_gateway
            from harness.hooks import hook_manager
            from models import Setting

            custom_prompt = ""
            s = db_session.query(Setting).filter(Setting.key == "custom_prompt").first()
            if s:
                custom_prompt = s.value

            industry = ""
            ind_s = db_session.query(Setting).filter(Setting.key == "industry_preset").first()
            if ind_s:
                industry = ind_s.value

            if agent_mode == "command":
                return await self._command_mode(user_message, db_session)

            role = self._infer_role(user_message)
            system_prompt = build_system_prompt(role, custom_prompt, industry=industry)

            tool_schemas = []
            max_perm = 0 if agent_mode == "light" else 4
            tool_schemas = skill_registry.get_tool_schemas(max_permission=max_perm)

            data_result = await skill_registry.execute("data_summary", {}, db_session=db_session)
            data_context = ""
            if data_result.success:
                data_context = build_context_message(tasks_summary=data_result.to_str())

            history = memory_manager.get_l1_memory(limit=10)
            ctx_mgr = ContextManager()
            messages = ctx_mgr.build_context(history, system_prompt, data_context)
            messages.append({"role": "user", "content": user_message})
            messages = ctx_mgr.truncate_if_needed(messages)

            self._transition(AgentState.PLANNING)

            model = None
            setting_model = db_session.query(Setting).filter(Setting.key == "ai_model_primary").first()
            if agent_mode == "light":
                fallback = db_session.query(Setting).filter(Setting.key == "ai_model_fallback").first()
                model = fallback.value if fallback else None

            while self._iterations < MAX_TOOL_ITERATIONS:
                self._iterations += 1

                response = await ai_client.chat_with_tools(
                    messages=messages,
                    tools=tool_schemas if tool_schemas else None,
                    model=model,
                )

                if response.get("type") == "tool_calls":
                    self._transition(AgentState.TOOL_USE)
                    tool_calls = response["tool_calls"]
                    for tc in tool_calls:
                        fn_name = tc["function"]["name"]
                        fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]

                        await hook_manager.pre_tool_call(fn_name, fn_args)

                        perm_ok = permission_gateway.check(fn_name, db_session)
                        if not perm_ok:
                            tool_result_str = f"Permission denied for skill '{fn_name}'"
                        else:
                            result = await skill_registry.execute(fn_name, fn_args, db_session=db_session)
                            tool_result_str = result.to_str()

                        await hook_manager.post_tool_call(fn_name, tool_result_str)

                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tc],
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_result_str,
                        })

                    self._transition(AgentState.OBSERVATION)
                    continue

                self._transition(AgentState.RESPONSE)
                final_text = response.get("content", "")

                self._transition(AgentState.MEMORY_UPDATE)
                try:
                    memory_manager.store_knowledge_from_conversation(user_message, final_text)
                except Exception:
                    pass

                self._transition(AgentState.DONE)
                return final_text

            return "思考步骤过多，已自动停止。请尝试更简洁的指令。"

        except Exception as e:
            self._transition(AgentState.ERROR)
            logger.error(f"AgentLoop error: {e}", exc_info=True)
            return await self._fallback_response(user_message, db_session)

    async def _command_mode(self, message: str, db_session) -> str:
        """Command mode: slash commands only, zero tokens."""
        from harness.skill_registry import skill_registry
        cmd_map = {
            "/今日待办": "today_tasks",
            "/逾期": "overdue_tasks",
            "/团队进度": "team_progress",
            "/日报": "daily_report",
            "/催办": "urge_overdue",
            "/本周数据": "weekly_data",
        }

        text = message.strip()

        if text.startswith("/评分"):
            parts = text.split(maxsplit=1)
            name = parts[1].strip() if len(parts) > 1 else ""
            if not name:
                return "用法: /评分 <员工姓名>"
            result = await skill_registry.execute("employee_score", {"employee_name": name}, db_session=db_session)
            return result.to_str()

        skill_name = cmd_map.get(text)
        if skill_name:
            result = await skill_registry.execute(skill_name, {}, db_session=db_session)
            return result.to_str()
        available = "\n".join([f"  {cmd}" for cmd in cmd_map.keys()])
        return f"可用命令:\n{available}\n  /评分 <姓名>\n\n切换到 Light/Full 模式以使用 AI 对话。"

    def _infer_role(self, message: str) -> str:
        msg = message.lower()
        if any(kw in msg for kw in ["目标", "战略", "规划", "决策", "分配"]):
            return "director"
        if any(kw in msg for kw in ["数据", "分析", "趋势", "对比", "统计", "报表"]):
            return "analyst"
        if any(kw in msg for kw in ["辅导", "培训", "成长", "建议", "改进", "短板"]):
            return "coach"
        if any(kw in msg for kw in ["任务", "拆解", "执行", "催办", "进度", "派发"]):
            return "executor"
        return "director"

    async def _fallback_response(self, message: str, db_session) -> str:
        """Keyword-based fallback when AI is unavailable."""
        from models import Task, Goal, KPIRecord, Employee
        if "任务" in message:
            tasks = db_session.query(Task).order_by(Task.created_at.desc()).limit(5).all()
            if tasks:
                lines = ["最近任务:"]
                for t in tasks:
                    s = t.status.value if hasattr(t.status, 'value') else t.status
                    lines.append(f"  • {t.title} [{s}] - {t.assignee_name or '未指派'}")
                return "\n".join(lines)
        if "目标" in message:
            goals = db_session.query(Goal).order_by(Goal.created_at.desc()).limit(5).all()
            if goals:
                lines = ["近期目标:"]
                for g in goals:
                    pct = round(g.current_value / g.target_value * 100) if g.target_value > 0 else 0
                    lines.append(f"  • {g.title} ({pct}%)")
                return "\n".join(lines)
        return "你好！我是千方百计AI管理助手。可用命令: /今日待办, /逾期, /团队进度, /日报, /催办"


agent_loop = AgentLoop()
