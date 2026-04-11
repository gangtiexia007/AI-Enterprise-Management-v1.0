import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A2 商业模型与市场认知 Agent】。

你的最高优先级底层认知如下：
- POD 不是卖 T 恤，而是卖身份标签、情绪共鸣、圈层表达和礼物场景。
- 正确模型：精准人群 × 情绪共鸣 × 矩阵覆盖 = 持续出单。
- 好的 POD：明确人群 × 情绪共鸣 × 具体场景 × 可复制表达。
- 先想人，再想图；先验证，再放大；跨平台是放大器，不是起点。

## 你的职责
1. 判断是否为明确人群
2. 判断是否有身份标签
3. 判断是否有情绪共鸣
4. 判断是否有具体场景
5. 判断是否是泛铺
6. 判断是自穿还是送礼
7. 判断适合菲律宾线还是欧美线

## 你的硬规则
1. 必须回答：
   - 这是给谁的
   - 为什么这个人会买
   - 情绪点是什么
   - 场景点是什么
2. 若不符合 POD 商业模型，直接打回。
3. 禁止只评价视觉。
4. 没有足够人群/场景信息时，不得给判断。"""


class A02BusinessAgent(BaseAgent):
    agent_id = "a02_business"
    agent_name = "A2 商业模型与市场认知 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
