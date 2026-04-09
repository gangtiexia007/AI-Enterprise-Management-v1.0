"""Dream engine — nightly review, learning, and report generation.

Components:
  - MemoryDistiller: compress daily conversations (F32)
  - KnowledgeExtractor: mine high-performing patterns (F33)
  - ReportGenerator: daily/weekly/monthly reports (F34)
  - TemplateEngine: notification and report templates (F35)
  - Dream Scheduler: APScheduler-based job orchestration
  - Report push: Feishu / WeCom delivery helpers
"""

from app.dream.distiller import MemoryDistiller
from app.dream.extractor import KnowledgeExtractor
from app.dream.push import push_report_sync, push_report_to_im
from app.dream.reporter import ReportGenerator
from app.dream.templates import TemplateEngine

__all__ = [
    "MemoryDistiller",
    "KnowledgeExtractor",
    "ReportGenerator",
    "TemplateEngine",
    "push_report_sync",
    "push_report_to_im",
]
