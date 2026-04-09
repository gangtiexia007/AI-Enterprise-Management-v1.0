"""Feishu integration client - stub implementation."""
import logging
from database import SessionLocal
from models import Setting, AuditLog
from datetime import datetime

logger = logging.getLogger(__name__)

def _get_setting(key: str, default: str = "") -> str:
    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default
    finally:
        db.close()

def _log_audit(action: str, detail: str):
    db = SessionLocal()
    try:
        db.add(AuditLog(action=action, detail=detail, actor="feishu_bot", created_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()

class FeishuClient:
    def is_enabled(self) -> bool:
        return _get_setting("feishu_enabled", "false").lower() == "true"

    def send_text_message(self, user_id: str, text: str) -> bool:
        if not self.is_enabled():
            logger.info(f"[Feishu STUB] text to {user_id}: {text[:50]}")
            return False
        _log_audit("feishu_send_text", f"to={user_id}, text={text[:100]}")
        logger.info(f"[Feishu] Would send text to {user_id}: {text[:50]}")
        return True

    def send_card_message(self, user_id: str, card: dict) -> bool:
        if not self.is_enabled():
            logger.info(f"[Feishu STUB] card to {user_id}")
            return False
        _log_audit("feishu_send_card", f"to={user_id}")
        logger.info(f"[Feishu] Would send card to {user_id}")
        return True

    def send_task_notification(self, employee_feishu_id: str, task_title: str, deadline: str = ""):
        msg = f"📋 新任务: {task_title}"
        if deadline:
            msg += f"\n⏰ 截止: {deadline}"
        return self.send_text_message(employee_feishu_id, msg)

    def send_reminder(self, employee_feishu_id: str, task_title: str, days_overdue: int):
        msg = f"⚠️ 催办: {task_title} 已逾期 {days_overdue} 天，请尽快处理。"
        return self.send_text_message(employee_feishu_id, msg)

    def send_daily_report(self, boss_feishu_id: str, report_text: str):
        return self.send_text_message(boss_feishu_id, f"📊 每日管理简报\n\n{report_text}")

feishu_client = FeishuClient()
