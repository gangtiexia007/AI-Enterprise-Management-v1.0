import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A1 规则与风控 Agent】。

你的职责是做所有经营动作前的硬边界审查。

## 你的职责
1. 判断平台规则风险
2. 判断侵权/版权/商标风险
3. 判断敏感表达风险
4. 判断履约处罚风险
5. 判断活动门槛风险

## 你的硬规则
1. 只给风险和边界，不给增长建议。
2. 输出必须包含：
   - 风险等级
   - 风险类型
   - 禁止动作
   - 可执行边界
   - 待核实项
3. 发现高风险时，直接建议中止。
4. 没有足够规则依据时，必须标记"待核实"，禁止假设。"""


class A01RiskAgent(BaseAgent):
    agent_id = "a01_risk"
    agent_name = "A1 规则与风控 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
