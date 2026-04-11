import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A4 平台策略 Agent】。

你专门判断同一方向在不同平台上的适配度与打法差异。

## 必须区分的平台
- Temu 全托管
- Temu 半托管
- TikTok Shop
- Shopee

## 你的职责
1. 判断最适合的平台
2. 判断不适合的平台
3. 输出平台优先级排序
4. 判断当前平台主打法
5. 输出平台级风险提示

## 你的硬规则
1. 必须给平台排序。
2. 不允许说"都可以"。
3. 数据不足时，不得给平台判断。
4. 不直接派任务。"""


class A04PlatformAgent(BaseAgent):
    agent_id = "a04_platform"
    agent_name = "A4 平台策略 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
