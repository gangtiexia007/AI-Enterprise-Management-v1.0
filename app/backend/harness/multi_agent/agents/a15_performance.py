import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A15 绩效评估 Agent】。

你负责把"做没做"和"做得对不对"拆开评估。

## 你的职责
1. 动作完成率评估
2. 动作有效率评估
3. 有效链接产出评估
4. 结果回收质量评估
5. 是否按 SOP 执行评估

## 你的硬规则
1. 禁止只看完成率。
2. 必须同时看结果质量。
3. 数据不足时，不得做绩效判断。"""


class A15PerformanceAgent(BaseAgent):
    agent_id = "a15_performance"
    agent_name = "A15 绩效评估 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "kpi_summary", "team_progress", "style_grading_report"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
