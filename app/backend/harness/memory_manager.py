"""
L1-L5 hierarchical memory management with distillation.

L1: Working memory (current conversation window)
L2: Recent summaries (auto-generated)
L3: Knowledge base (structured knowledge articles)
L4: Long-term patterns (distilled from conversations)
L5: Raw conversation archive
"""
import json
import logging
from typing import List, Dict, Optional
from database import SessionLocal
from models import Conversation, Knowledge, KnowledgeCategory, MemoryEntry
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryManager:
    def get_l1_memory(self, limit: int = 20) -> List[Dict]:
        """Get recent conversation messages (working memory)."""
        db = SessionLocal()
        try:
            rows = db.query(Conversation).order_by(Conversation.id.desc()).limit(limit).all()
            return [{"role": r.role, "content": r.content} for r in reversed(rows)]
        finally:
            db.close()

    def get_l2_summary(self, limit: int = 5) -> List[Dict]:
        """Get recent conversation summaries."""
        db = SessionLocal()
        try:
            entries = db.query(MemoryEntry).filter(
                MemoryEntry.level == 2,
            ).order_by(MemoryEntry.created_at.desc()).limit(limit).all()
            return [{"title": e.title, "content": e.content[:300]} for e in entries]
        finally:
            db.close()

    def get_l3_knowledge(self, category: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Get structured knowledge articles."""
        db = SessionLocal()
        try:
            q = db.query(Knowledge)
            if category:
                q = q.filter(Knowledge.category == category)
            items = q.order_by(Knowledge.updated_at.desc()).limit(limit).all()
            return [{"title": k.title, "content": k.content[:200], "category": k.category.value if hasattr(k.category, 'value') else str(k.category)} for k in items]
        finally:
            db.close()

    def get_l4_patterns(self, limit: int = 10) -> List[Dict]:
        """Get distilled long-term patterns."""
        db = SessionLocal()
        try:
            entries = db.query(MemoryEntry).filter(
                MemoryEntry.level == 4,
            ).order_by(MemoryEntry.created_at.desc()).limit(limit).all()
            return [{"title": e.title, "content": e.content[:300], "confidence": e.confidence} for e in entries]
        finally:
            db.close()

    def store_knowledge_from_conversation(self, user_msg: str, ai_response: str):
        """Quick extraction: if AI response contains actionable knowledge, store it."""
        if len(ai_response) < 100:
            return

        keywords = ["SOP", "流程", "规则", "注意事项", "禁忌", "经验", "案例"]
        has_knowledge = any(kw in ai_response for kw in keywords)
        if not has_knowledge:
            return

        db = SessionLocal()
        try:
            title = user_msg[:100] if len(user_msg) > 0 else "AI提取知识"
            category = KnowledgeCategory.CASE
            if any(kw in ai_response for kw in ["SOP", "流程", "步骤"]):
                category = KnowledgeCategory.SOP
            elif any(kw in ai_response for kw in ["规则", "规定"]):
                category = KnowledgeCategory.RULE
            elif any(kw in ai_response for kw in ["禁忌", "不能", "不要"]):
                category = KnowledgeCategory.TABOO

            item = Knowledge(
                title=title,
                content=ai_response[:2000],
                category=category,
                source="ai_extraction",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(item)
            db.commit()
        except Exception as e:
            logger.debug(f"Knowledge extraction skipped: {e}")
            db.rollback()
        finally:
            db.close()

    def distill_conversations(self, batch_size: int = 50):
        """L5 conversations → L4 distilled patterns via AI."""
        db = SessionLocal()
        try:
            last_distill = db.query(MemoryEntry).filter(
                MemoryEntry.source_type == "conversation",
            ).order_by(MemoryEntry.created_at.desc()).first()

            cutoff = last_distill.created_at if last_distill else datetime.utcnow() - timedelta(days=7)

            conversations = db.query(Conversation).filter(
                Conversation.created_at > cutoff,
            ).order_by(Conversation.id.asc()).limit(batch_size).all()

            if len(conversations) < 10:
                return

            conv_text = ""
            source_ids = []
            for c in conversations:
                role = "用户" if c.role == "user" else "AI"
                conv_text += f"{role}: {c.content[:150]}\n"
                source_ids.append(c.id)

            try:
                from harness.ai_client import ai_client
                import asyncio

                prompt = f"""分析以下对话记录，提取出有价值的管理洞察和模式（如果有的话）。
用JSON数组格式返回，每个元素包含 title 和 content 字段。
如果没有有价值的洞察，返回空数组 []。

对话记录:
{conv_text[:3000]}

请返回JSON数组:"""

                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(ai_client.chat(
                    [{"role": "system", "content": "你是知识提取助手，从对话中提取管理洞察和模式。只返回JSON。"},
                     {"role": "user", "content": prompt}],
                    max_tokens=800,
                ))
                loop.close()

                try:
                    start = response.find("[")
                    end = response.rfind("]") + 1
                    if start >= 0 and end > start:
                        insights = json.loads(response[start:end])
                    else:
                        insights = []
                except (json.JSONDecodeError, ValueError):
                    insights = []

                for insight in insights[:5]:
                    if isinstance(insight, dict) and insight.get("title"):
                        db.add(MemoryEntry(
                            level=4,
                            title=insight["title"][:300],
                            content=insight.get("content", "")[:2000],
                            source_type="conversation",
                            source_ids=json.dumps(source_ids[:10]),
                            confidence=0.7,
                            created_at=datetime.utcnow(),
                        ))

                db.commit()
                logger.info(f"Distilled {len(insights)} insights from {len(conversations)} conversations")

            except Exception as e:
                logger.error(f"AI distillation failed: {e}")

        finally:
            db.close()

    def auto_extract_knowledge(self, conversation_id: int):
        """Extract knowledge from a specific conversation using AI."""
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conv or conv.role != "assistant":
                return

            prev = db.query(Conversation).filter(
                Conversation.id < conversation_id,
                Conversation.role == "user",
            ).order_by(Conversation.id.desc()).first()

            if prev:
                self.store_knowledge_from_conversation(prev.content, conv.content)
        finally:
            db.close()


memory_manager = MemoryManager()
