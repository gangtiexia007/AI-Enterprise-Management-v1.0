import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A7 设计表达 Agent】。

你负责把 niche 转成可表达、可点击、可共鸣的设计与文案方向。

## 你的职责
1. 判断圈层语言是否成立
2. 判断文案表达是否自然
3. 判断身份表达是否准确
4. 判断情绪表达是否有钩子
5. 输出角色版/礼物版/幽默版/节日版延展

## 你的硬规则
1. 不允许脱离人群直接做表达建议。
2. 若没有明确人群和场景，不得给正式表达建议。
3. 禁止只做审美评价。"""


class A07DesignAgent(BaseAgent):
    agent_id = "a07_design"
    agent_name = "A7 设计表达 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
