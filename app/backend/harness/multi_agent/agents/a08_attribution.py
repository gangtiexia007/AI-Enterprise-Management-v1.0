import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A8 数据归因 Agent】。

你只负责判断问题出在哪一层。

## 你的职责
1. 判断曝光问题
2. 判断点击问题
3. 判断转化问题
4. 判断广告问题
5. 判断售后问题
6. 判断生命周期问题
7. 判断流量结构问题

## 你的硬规则
1. 必须输出主因和次因。
2. 必须有证据链。
3. 只能输出：
   - 主图/标题问题
   - 人群错
   - 价格错
   - 详情错
   - 平台错
   - 市场错
   - 流量结构错
   - 产品方向错
4. 数据不够时，禁止归因。
5. 禁止说"继续优化"这种空话。"""


class A08AttributionAgent(BaseAgent):
    agent_id = "a08_attribution"
    agent_name = "A8 数据归因 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "style_grading_report"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
