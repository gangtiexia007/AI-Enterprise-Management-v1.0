"""L1-L5 hierarchical memory management."""
from typing import List, Dict, Optional
from database import SessionLocal
from models import Conversation, Knowledge, KnowledgeCategory
from datetime import datetime

class MemoryManager:
    """
    L1: Working memory (current conversation)
    L2: Recent summaries (last N conversations)
    L3: Knowledge base (structured knowledge)
    L4: Long-term patterns (periodic distillation)
    L5: Raw conversation archive
    """

    def get_l1_memory(self, limit: int = 20) -> List[Dict]:
        db = SessionLocal()
        try:
            rows = db.query(Conversation).order_by(Conversation.id.desc()).limit(limit).all()
            return [{"role": r.role, "content": r.content} for r in reversed(rows)]
        finally:
            db.close()

    def get_l3_knowledge(self, category: Optional[str] = None, limit: int = 10) -> List[Dict]:
        db = SessionLocal()
        try:
            q = db.query(Knowledge)
            if category:
                q = q.filter(Knowledge.category == category)
            items = q.order_by(Knowledge.updated_at.desc()).limit(limit).all()
            return [{"title": k.title, "content": k.content[:200], "category": k.category.value if hasattr(k.category, 'value') else str(k.category)} for k in items]
        finally:
            db.close()

    def store_knowledge_from_conversation(self, title: str, content: str, category: str = "case"):
        db = SessionLocal()
        try:
            item = Knowledge(
                title=title,
                content=content,
                category=KnowledgeCategory(category) if category in [e.value for e in KnowledgeCategory] else KnowledgeCategory.CASE,
                source="ai_extraction",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(item)
            db.commit()
        finally:
            db.close()

memory_manager = MemoryManager()
