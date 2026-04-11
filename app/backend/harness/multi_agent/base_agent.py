"""Base class for all POD multi-agent system agents."""
import json
import logging
from typing import Any

from harness.ai_client import ai_client
from harness.multi_agent.schemas import AgentInput, AgentOutput, RiskLevel, Confidence, DataSufficiency

logger = logging.getLogger(__name__)

MAX_AGENT_TOOL_ITERATIONS = 5


class BaseAgent:
    agent_id: str = ""
    agent_name: str = ""
    system_prompt: str = ""
    allowed_tools: list[str] = []
    enabled: bool = True
    description: str = ""

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)

    @staticmethod
    def _find_prior(prior_outputs, agent_id: str):
        """从 list 或 dict 格式的 prior_outputs 中查找指定 agent 的输出。"""
        if isinstance(prior_outputs, dict):
            return prior_outputs.get(agent_id)
        if isinstance(prior_outputs, list):
            for out in prior_outputs:
                if isinstance(out, AgentOutput) and out.agent_name and agent_id in out.agent_name:
                    return out
                if isinstance(out, dict) and out.get("agent_name", "") and agent_id in out.get("agent_name", ""):
                    return out
        return None

    async def _base_run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        from harness.skill_registry import skill_registry
        from harness.permissions import permission_gateway
        from harness.hooks import hook_manager

        messages = self._build_messages(input_data, context)

        all_schemas = skill_registry.get_tool_schemas(max_permission=2)
        tool_schemas = [s for s in all_schemas if s["function"]["name"] in self.allowed_tools] if self.allowed_tools else []

        total_tokens = 0

        for iteration in range(MAX_AGENT_TOOL_ITERATIONS):
            if tool_schemas:
                response = await ai_client.chat_with_tools(messages=messages, tools=tool_schemas, temperature=0.4)
                total_tokens += getattr(ai_client, '_last_usage_tokens', 0)
            else:
                raw = await ai_client.chat(messages, temperature=0.4, max_tokens=3000)
                total_tokens += getattr(ai_client, '_last_usage_tokens', 0)
                output = self._parse_output(raw, input_data)
                output.total_tokens = total_tokens
                return output

            if response.get("type") == "tool_calls":
                tool_calls = response["tool_calls"]
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args_raw = tc["function"]["arguments"]
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw

                    await hook_manager.pre_tool_call(fn_name, fn_args)

                    if fn_name not in self.allowed_tools:
                        tool_result_str = f"Tool '{fn_name}' not in allowed_tools for {self.agent_id}"
                    else:
                        perm_result = permission_gateway.check(fn_name, db_session)
                        if perm_result == "pending_approval":
                            tool_result_str = f"技能 '{fn_name}' 需要审批确认（P3），已提交审批流程，请在审批中心处理。"
                        elif not perm_result:
                            tool_result_str = f"Permission denied for '{fn_name}'"
                        else:
                            result = await skill_registry.execute(fn_name, fn_args, db_session=db_session)
                            tool_result_str = result.to_str()

                    await hook_manager.post_tool_call(fn_name, tool_result_str)

                    messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result_str})
                continue

            raw_content = response.get("content", "")
            output = self._parse_output(raw_content, input_data)
            output.total_tokens = total_tokens
            return output

        output = self._parse_output("工具调用次数超限，已自动停止。", input_data)
        output.total_tokens = total_tokens
        return output

    def _build_messages(self, input_data: AgentInput, context: dict) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]

        prior_summary = context.get("prior_outputs_summary")
        if prior_summary:
            messages.append({
                "role": "system",
                "content": "前序 Agent 结论(摘要):\n" + prior_summary,
            })
        else:
            prior_outputs = context.get("prior_outputs", {})
            if prior_outputs:
                summary_parts = []
                items = prior_outputs.items() if isinstance(prior_outputs, dict) else enumerate(prior_outputs)
                for _key, out in items:
                    if isinstance(out, AgentOutput):
                        summary_parts.append(f"[{out.agent_name}] 判断: {out.judgment}")
                    elif isinstance(out, dict):
                        summary_parts.append(f"[{out.get('agent_name', _key)}] 判断: {out.get('judgment', '')}")
                if summary_parts:
                    messages.append({
                        "role": "system",
                        "content": "前序 Agent 结论:\n" + "\n".join(summary_parts),
                    })

        memory = context.get("memory", {})
        if memory:
            memory_parts = []
            for k in memory.get("knowledge", []):
                memory_parts.append(f"- [{k.get('category','')}] {k.get('title','')}: {k.get('content','')}")
            for p in memory.get("patterns", []):
                memory_parts.append(f"- [模式] {p.get('title','')}: {p.get('content','')}")
            if memory_parts:
                messages.append({
                    "role": "system",
                    "content": "相关知识与历史模式:\n" + "\n".join(memory_parts[:10]),
                })

        alerts = context.get("active_alerts", [])
        if alerts:
            alert_parts = [f"- [{a['action']}] {a['detail']} ({a['time']})" for a in alerts[:5]]
            messages.append({
                "role": "system",
                "content": "系统规则检测到的活跃告警:\n" + "\n".join(alert_parts),
            })

        user_content = input_data.to_prompt_context()
        messages.append({"role": "user", "content": user_content})
        return messages

    def _parse_output(self, raw: str, input_data: AgentInput) -> AgentOutput:
        output = AgentOutput(
            agent_name=self.agent_name,
            task_type=input_data.task_type,
            raw_response=raw,
        )

        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                first_nl = cleaned.index("\n")
                last_fence = cleaned.rfind("```")
                cleaned = cleaned[first_nl + 1:last_fence].strip()
            data = json.loads(cleaned)

            if "judgment" in data:
                output.judgment = data["judgment"]
            if "escalate_to" in data:
                output.escalate_to = data["escalate_to"]
            if "data_sufficiency" in data:
                try:
                    output.data_sufficiency = DataSufficiency(data["data_sufficiency"])
                except ValueError:
                    pass
            if "confidence" in data:
                try:
                    output.confidence = Confidence(data["confidence"])
                except ValueError:
                    pass
            if "risk_level" in data:
                try:
                    output.risk_level = RiskLevel(data["risk_level"])
                except ValueError:
                    pass

            for key in (
                "missing_fields", "evidence", "risk_notes", "next_actions",
                "memory_writeback", "notes",
            ):
                if key in data and isinstance(data[key], list):
                    setattr(output, key, data[key])
            if "scores" in data and isinstance(data["scores"], dict):
                output.scores = data["scores"]
            if "need_escalation" in data:
                output.need_escalation = bool(data["need_escalation"])
        except (json.JSONDecodeError, ValueError):
            output.judgment = raw

        return output
