import logging
from datetime import datetime
from harness.multi_agent.base_agent import BaseAgent
from harness.multi_agent.schemas import AgentInput, AgentOutput

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是【A16 记忆与知识库 Agent】。

你负责统一管理长期记忆和知识库写入与召回。

## 你的职责
1. 结构化写入规则记忆
2. 结构化写入 SOP 记忆
3. 结构化写入案例记忆
4. 结构化写入结果记忆
5. 结构化写入反例记忆
6. 为其他 Agent 做条件化召回

## 你的硬规则
1. 只有经过 A14 复盘沉淀确认的内容才可长期入库。
2. 不允许将未经验证结论写入长期知识库。
3. 每条记忆必须带适用条件。"""

MEMORY_TYPE_TO_CATEGORY = {
    "rule": "rule",
    "sop": "sop",
    "case": "case",
    "result": "case",
    "anti_case": "taboo",
}


class A16MemoryAgent(BaseAgent):
    agent_id = "a16_memory"
    agent_name = "A16 记忆与知识库 Agent"
    system_prompt = SYSTEM_PROMPT
    allowed_tools = ["search_knowledge"]

    async def run(self, input_data: AgentInput, context: dict, db_session) -> AgentOutput:
        output = await self._base_run(input_data, context, db_session)

        writeback_items = context.get("memory_writeback", [])
        if not writeback_items:
            prior = context.get("prior_outputs", {})
            a14_out = self._find_prior(prior, "a14_review")
            if a14_out is not None:
                if isinstance(a14_out, AgentOutput):
                    writeback_items = a14_out.memory_writeback
                elif isinstance(a14_out, dict):
                    writeback_items = a14_out.get("memory_writeback", [])

        if writeback_items:
            written = self._write_memory_entries(writeback_items, db_session)
            output.notes.append(f"已写入 {written} 条长期记忆")

        return output

    def _write_memory_entries(self, items: list, db_session) -> int:
        """将经过 A14 确认的记忆条目写入 Knowledge 表。"""
        from models import Knowledge, KnowledgeCategory

        written = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            if not title:
                continue

            mem_type = item.get("memory_type", "case")
            category_str = MEMORY_TYPE_TO_CATEGORY.get(mem_type, "case")
            try:
                category = KnowledgeCategory(category_str)
            except ValueError:
                category = KnowledgeCategory.CASE

            content_parts = []
            for key in ("action", "result", "why_it_worked_or_failed"):
                val = item.get(key, "")
                if val:
                    content_parts.append(f"{key}: {val}")

            conditions = item.get("conditions", [])
            if conditions:
                content_parts.append(f"适用条件: {', '.join(conditions)}")
            for tag_key in ("platform", "market", "persona", "niche"):
                tag_val = item.get(tag_key, "")
                if tag_val:
                    content_parts.append(f"{tag_key}: {tag_val}")

            entry = Knowledge(
                category=category,
                title=title,
                content="\n".join(content_parts),
                source="a14_review",
                created_at=datetime.utcnow(),
            )
            db_session.add(entry)
            written += 1
            logger.info("A16 写入记忆: [%s] %s", mem_type, title)

        if written > 0:
            try:
                db_session.commit()
            except Exception:
                logger.exception("A16 记忆写入提交失败")
                db_session.rollback()
                return 0

        return written
