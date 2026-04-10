"""
Feishu integration client — real implementation using Open API.

Supports:
- Tenant access token management (auto-refresh)
- Text / card / interactive messages via im/v1/messages
- Card templates for task notifications, reminders, reports
- Event-style feedback collection (webhook-based)
"""
import json
import time
import logging
from typing import Optional
import httpx

from database import SessionLocal
from models import Setting, AuditLog
from datetime import datetime

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


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
        db.add(AuditLog(action=action, detail=detail, actor="feishu_bot", resource_type="feishu", created_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()


class FeishuClient:
    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def is_enabled(self) -> bool:
        return _get_setting("feishu_enabled", "false").lower() == "true"

    def _get_tenant_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token

        app_id = _get_setting("feishu_app_id")
        app_secret = _get_setting("feishu_app_secret")
        if not app_id or not app_secret:
            raise ValueError("飞书 App ID/Secret 未配置")

        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise ValueError(f"获取飞书 token 失败: {data.get('msg')}")
            self._token = data["tenant_access_token"]
            self._token_expires = time.time() + data.get("expire", 7200) - 60
            return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_tenant_token()}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _detect_id_type(user_id: str) -> str:
        """Auto-detect id_type from prefix: on_ → union_id, ou_ → open_id, default open_id."""
        if user_id.startswith("on_"):
            return "union_id"
        if user_id.startswith("ou_"):
            return "open_id"
        return "open_id"

    def send_text_message(self, user_id: str, text: str, id_type: str = "") -> bool:
        id_type = id_type or self._detect_id_type(user_id)
        if not self.is_enabled():
            logger.info(f"[Feishu STUB] text→{user_id}: {text[:80]}")
            _log_audit("feishu_stub_text", f"to={user_id}, text={text[:100]}")
            return False
        if not user_id:
            logger.warning("send_text_message: empty user_id")
            return False
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{FEISHU_BASE}/im/v1/messages?receive_id_type={id_type}",
                    headers=self._headers(),
                    json={
                        "receive_id": user_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": text}),
                    },
                )
                data = resp.json()
                ok = data.get("code") == 0
                if ok:
                    _log_audit("feishu_send_text", f"to={user_id}, text={text[:100]}")
                else:
                    logger.error(f"Feishu send_text failed: {data}")
                return ok
        except Exception as e:
            logger.error(f"Feishu send_text error: {e}")
            return False

    def send_card_message(self, user_id: str, card: dict, id_type: str = "") -> bool:
        id_type = id_type or self._detect_id_type(user_id)
        if not self.is_enabled():
            logger.info(f"[Feishu STUB] card→{user_id}")
            _log_audit("feishu_stub_card", f"to={user_id}")
            return False
        if not user_id:
            return False
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{FEISHU_BASE}/im/v1/messages?receive_id_type={id_type}",
                    headers=self._headers(),
                    json={
                        "receive_id": user_id,
                        "msg_type": "interactive",
                        "content": json.dumps(card),
                    },
                )
                data = resp.json()
                ok = data.get("code") == 0
                if ok:
                    _log_audit("feishu_send_card", f"to={user_id}")
                else:
                    logger.error(f"Feishu send_card failed: {data}")
                return ok
        except Exception as e:
            logger.error(f"Feishu send_card error: {e}")
            return False

    # ───── Card Templates ─────

    def build_task_card(self, task_title: str, description: str, deadline: str, assignee: str) -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "📋 新任务通知"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**任务**: {task_title}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**描述**: {description or '无'}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**负责人**: {assignee}　|　**截止日期**: {deadline or '无'}"}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "请在截止日期前回复完成反馈，直接回复此消息即可。"}]},
            ],
        }

    def build_reminder_card(self, task_title: str, days_overdue: int, assignee: str) -> dict:
        urgency = "🔴 紧急" if days_overdue > 3 else "🟡 催办"
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": f"{urgency} 任务催办"}, "template": "red" if days_overdue > 3 else "yellow"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**任务**: {task_title}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**负责人**: {assignee}　|　**已逾期**: {days_overdue} 天"}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "请尽快处理并回复进度。"}]},
            ],
        }

    def build_report_card(self, title: str, content: str, date_str: str) -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": f"📊 {title}"}, "template": "purple"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": f"报告日期: {date_str} | 千方百计AI"}]},
            ],
        }

    def build_approval_card(self, task_title: str, detail: str) -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "⚠️ 逾期处理需您决策"}, "template": "orange"},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**任务**: {task_title}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": detail}},
                {"tag": "hr"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "请在 Dashboard 审批中心处理。"}]},
            ],
        }

    # ───── High-level Methods ─────

    def send_task_notification(self, employee_feishu_id: str, task_title: str, description: str = "", deadline: str = "", assignee: str = "") -> bool:
        card = self.build_task_card(task_title, description, deadline, assignee)
        return self.send_card_message(employee_feishu_id, card)

    def send_reminder(self, employee_feishu_id: str, task_title: str, days_overdue: int, assignee: str = "") -> bool:
        card = self.build_reminder_card(task_title, days_overdue, assignee)
        return self.send_card_message(employee_feishu_id, card)

    def send_daily_report(self, boss_feishu_id: str, report_text: str) -> bool:
        from datetime import date
        card = self.build_report_card("每日管理简报", report_text, str(date.today()))
        return self.send_card_message(boss_feishu_id, card)

    def send_weekly_report(self, boss_feishu_id: str, report_text: str) -> bool:
        from datetime import date
        card = self.build_report_card("周度管理报告", report_text, str(date.today()))
        return self.send_card_message(boss_feishu_id, card)

    def send_approval_request(self, boss_feishu_id: str, task_title: str, detail: str) -> bool:
        card = self.build_approval_card(task_title, detail)
        return self.send_card_message(boss_feishu_id, card)

    def send_status_notification(self, user_id: str, title: str, detail: str) -> bool:
        text = f"📌 {title}\n\n{detail}"
        return self.send_text_message(user_id, text)

    def send_text_to_chat(self, chat_id: str, text: str) -> bool:
        """Send a text message to a chat (by chat_id, supports both p2p and group)."""
        if not self.is_enabled():
            logger.info(f"[Feishu STUB] chat→{chat_id}: {text[:80]}")
            _log_audit("feishu_stub_chat", f"chat_id={chat_id}, text={text[:100]}")
            return False
        if not chat_id:
            logger.warning("send_text_to_chat: empty chat_id")
            return False
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
                    headers=self._headers(),
                    json={
                        "receive_id": chat_id,
                        "msg_type": "text",
                        "content": json.dumps({"text": text}),
                    },
                )
                data = resp.json()
                ok = data.get("code") == 0
                if ok:
                    _log_audit("feishu_chat_reply", f"chat_id={chat_id}, text={text[:100]}")
                else:
                    logger.error(f"Feishu send_text_to_chat failed: {data}")
                return ok
        except Exception as e:
            logger.error(f"Feishu send_text_to_chat error: {e}")
            return False

    def send_card_to_chat(self, chat_id: str, card: dict) -> bool:
        """Send a card message to a chat_id."""
        if not self.is_enabled():
            logger.info(f"[Feishu STUB] card-chat→{chat_id}")
            return False
        if not chat_id:
            return False
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(
                    f"{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id",
                    headers=self._headers(),
                    json={
                        "receive_id": chat_id,
                        "msg_type": "interactive",
                        "content": json.dumps(card),
                    },
                )
                data = resp.json()
                ok = data.get("code") == 0
                if not ok:
                    logger.error(f"Feishu send_card_to_chat failed: {data}")
                return ok
        except Exception as e:
            logger.error(f"Feishu send_card_to_chat error: {e}")
            return False


feishu_client = FeishuClient()
