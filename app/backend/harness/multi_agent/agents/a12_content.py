import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A12 内容与活动 Agent】。

你专门负责内容、达人、活动、节点节奏。

## 你的职责
1. 内容方向设计
2. 达人/联盟方向
3. 节点节奏
4. 活动报名节奏
5. 内容型成交打法

## 你的硬规则
1. 必须明确平台和市场。
2. 必须明确内容目标。
3. 数据不足时，只能输出候选内容方向，不得输出经营建议。"""


class A12ContentAgent(BaseAgent):
    agent_id = "a12_content"
    agent_name = "A12 内容与活动 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        if not input_data.platform or not input_data.market:
            return AgentOutput(
                agent_name=self.agent_name,
                task_type=input_data.task_type,
                data_sufficiency="insufficient",
                judgment="平台和市场信息缺失，无法给出内容与活动建议。",
                confidence="high",
                missing_fields=[
                    f for f in ["platform", "market"]
                    if not getattr(input_data, f, "")
                ],
            )
        return await self._base_run(input_data, context, db_session)
