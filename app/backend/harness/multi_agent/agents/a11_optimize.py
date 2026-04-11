import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A11 链接优化 Agent】。

你专门负责已有链接的优化动作定义。

## 你的职责
1. 定义改标题
2. 定义改主图
3. 定义改卖点
4. 定义改详情
5. 定义改价格
6. 定义改变体

## 你的硬规则
1. 必须建立在 A8 数据归因基础上。
2. 没有归因，不得给优化动作。
3. 必须定义优化后需要回收的数据。"""


class A11OptimizeAgent(BaseAgent):
    agent_id = "a11_optimize"
    agent_name = "A11 链接优化 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "style_grading_report"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        prior = context.get("prior_outputs", {})
        a8 = self._find_prior(prior, "a08_attribution")
        if a8 is None:
            return AgentOutput(
                agent_name=self.agent_name,
                task_type=input_data.task_type,
                data_sufficiency="insufficient",
                judgment="缺少 A8 数据归因结论，无法给出优化动作。",
                confidence="high",
                risk_level="medium",
                missing_fields=["a08_attribution_output"],
            )
        return await self._base_run(input_data, context, db_session)
