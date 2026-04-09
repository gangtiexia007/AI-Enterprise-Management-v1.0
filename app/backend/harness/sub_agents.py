"""SubAgentRunner with four specialized roles."""
from typing import Optional
from harness.prompt_templates import build_system_prompt, ROLE_TEMPLATES

class SubAgentRunner:
    ROLES = list(ROLE_TEMPLATES.keys())

    def select_role(self, user_input: str) -> str:
        input_lower = user_input.lower()
        if any(kw in input_lower for kw in ["目标", "战略", "规划", "决策", "分配"]):
            return "director"
        if any(kw in input_lower for kw in ["数据", "分析", "趋势", "对比", "统计", "报表"]):
            return "analyst"
        if any(kw in input_lower for kw in ["辅导", "培训", "成长", "建议", "改进", "短板"]):
            return "coach"
        if any(kw in input_lower for kw in ["任务", "拆解", "执行", "催办", "进度", "派发"]):
            return "executor"
        return "director"

    def get_system_prompt(self, role: str, custom_prompt: str = "") -> str:
        return build_system_prompt(role, custom_prompt)

sub_agent_runner = SubAgentRunner()
