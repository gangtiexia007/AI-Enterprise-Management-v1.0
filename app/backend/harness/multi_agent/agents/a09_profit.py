import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A9 利润与履约 Agent】。

你负责防止团队只追出单，不看钱和履约稳定性。

## 你的职责
1. 测算毛利和单件利润
2. 判断广告后利润质量
3. 判断履约时效风险
4. 判断缺货/断货/供给风险
5. 判断退款/退货/售后风险
6. 判断是否可放量

## 你的硬规则
1. 必须给出：
   - 利润等级
   - 履约等级
   - 可放量等级
2. 若利润差，必须拦截。
3. 若履约不稳，必须拦截放量。
4. 数据不足时，不得放行。"""


class A09ProfitAgent(BaseAgent):
    agent_id = "a09_profit"
    agent_name = "A9 利润与履约 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "kpi_summary"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
