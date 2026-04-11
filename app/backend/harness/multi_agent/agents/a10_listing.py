import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A10 上新策略 Agent】。

你负责把通过评估的方向变成上新策略。

## 你的职责
1. 决定先上哪个平台
2. 决定先上哪个市场
3. 决定一次上多少款
4. 决定单点验证还是矩阵验证
5. 决定上新批次和节奏

## 你的硬规则
1. 必须以前序 Agent 已放行为前提。
2. 若前序任一关键 Agent 未放行，不得给上新策略。
3. 必须给出批次、数量、节奏。"""


class A10ListingAgent(BaseAgent):
    agent_id = "a10_listing"
    agent_name = "A10 上新策略 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["query_bitable", "niche_status"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        prior = context.get("prior_outputs", {})
        blocked = self._check_prior_approvals(prior)
        if blocked:
            return AgentOutput(
                agent_name=self.agent_name,
                task_type=input_data.task_type,
                data_sufficiency="insufficient",
                judgment=f"前序 Agent 未放行，不可出上新策略。拦截原因: {blocked}",
                confidence="high",
                risk_level="high",
            )
        return await self._base_run(input_data, context, db_session)

    def _check_prior_approvals(self, prior) -> str:
        """检查前序关键 Agent 是否已放行，返回拦截原因或空字符串。"""
        critical_agents = {
            "a01_risk": "规则与风控",
            "a09_profit": "利润与履约",
        }
        reasons = []
        for agent_id, label in critical_agents.items():
            out = self._find_prior(prior, agent_id)
            if out is None:
                continue
            risk = out.risk_level if isinstance(out, AgentOutput) else out.get("risk_level", "")
            if risk == "high":
                reasons.append(f"{label} 判定高风险")
        return "; ".join(reasons)
