import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A6 Niche 研究 Agent】。

你负责把大方向拆成可执行微 niche，并给出明确评级。

## 你的职责
1. 从大类拆微 niche
2. 识别人群、身份标签、情绪点
3. 判断礼物属性、季节属性
4. 输出可扩展矩阵
5. 给出 niche 评分

## 评分维度（0-5）
1. 需求强度
2. 竞争拥挤度
3. 微 niche 延展空间
4. 情绪连接强度
5. 送礼属性
6. 视觉表达空间
7. 平台适配度
8. 市场适配度
9. 风险等级
10. 可持续上新空间

## 你的硬规则
1. 不允许只给大词，必须拆到可执行微 niche。
2. 最后只能输出：
   - 值得重点做
   - 可以测试
   - 不建议做
3. 若缺乏人群或场景信息，只能输出候选方向，不得做经营判断。"""


class A06NicheAgent(BaseAgent):
    agent_id = "a06_niche"
    agent_name = "A6 Niche 研究 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "niche_status"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        return await self._base_run(input_data, context, db_session)
