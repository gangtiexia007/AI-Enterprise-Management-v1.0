import logging
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A14 复盘沉淀 Agent】。

你负责把一次次结果沉淀成以后可复用知识。

## 你的职责
1. 沉淀 SOP
2. 沉淀案例
3. 沉淀反例
4. 沉淀平台经验
5. 沉淀市场经验
6. 沉淀有效表达

## 你的硬规则
1. 只沉淀可复用内容。
2. 废话、情绪化表述、不完整经验不得入库。
3. 必须标注适用平台、市场、人群、条件。

## 记忆写入结构
当有值得沉淀的内容时，在 memory_writeback 字段中输出以下结构：
[
  {
    "memory_type": "rule|sop|case|result|anti_case",
    "title": "标题",
    "platform": "适用平台",
    "market": "适用市场",
    "persona": "适用人群",
    "niche": "相关niche",
    "conditions": ["适用条件1", "适用条件2"],
    "action": "执行了什么动作",
    "result": "结果是什么",
    "why_it_worked_or_failed": "为什么有效或失败",
    "reusable": true
  }
]"""


class A14ReviewAgent(BaseAgent):
    agent_id = "a14_review"
    agent_name = "A14 复盘沉淀 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        output = await self._base_run(input_data, context, db_session)
        valid = []
        for item in output.memory_writeback:
            if isinstance(item, dict) and item.get("title") and item.get("reusable", True):
                valid.append(item)
            else:
                logger.debug("过滤不可复用或不完整的沉淀条目")
        output.memory_writeback = valid
        if valid:
            output.notes.append(f"产出 {len(valid)} 条待沉淀记忆，待 A16 写入")
        return output
