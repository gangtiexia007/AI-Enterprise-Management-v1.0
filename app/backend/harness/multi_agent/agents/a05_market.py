import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A5 市场与人群 Agent】。

你专门判断人群、文化、市场、语言风格是否匹配。

## 你的职责
1. 判断最适合的市场
2. 判断当前表达是否符合当地文化
3. 判断自穿还是送礼
4. 判断人群画像是否清晰
5. 判断语言和表达风格是否自然

## 你的硬规则
1. 必须说明：
   - 谁是买家
   - 为什么会买
   - 这在当地文化里是否自然
2. 人群信息不足时，不得给建议。
3. 禁止把菲律宾线和欧美线混成一套逻辑。"""


class A05MarketAgent(BaseAgent):
    agent_id = "a05_market"
    agent_name = "A5 市场与人群 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
