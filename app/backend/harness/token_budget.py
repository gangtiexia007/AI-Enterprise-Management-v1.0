"""
Token Budget Management — monthly/daily budget tracking with alerts and model degradation.
"""
import logging
from datetime import datetime, date
from typing import Optional

from database import SessionLocal
from models import TokenBudget, TokenUsage, Setting

logger = logging.getLogger(__name__)


def _get_setting(key: str, default: str = "") -> str:
    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default
    finally:
        db.close()


class TokenBudgetManager:
    def get_or_create_monthly(self, period: Optional[str] = None) -> dict:
        period = period or date.today().strftime("%Y-%m")
        db = SessionLocal()
        try:
            budget = db.query(TokenBudget).filter(
                TokenBudget.period == period,
                TokenBudget.period_type == "monthly",
            ).first()

            if not budget:
                raw = _get_setting("token_budget_monthly", "5000000")
                monthly_budget = int(raw) if raw else 5000000
                budget = TokenBudget(
                    period=period,
                    period_type="monthly",
                    budget_tokens=monthly_budget,
                    used_tokens=0,
                    created_at=datetime.utcnow(),
                )
                db.add(budget)
                db.commit()
                db.refresh(budget)

            return {
                "period": budget.period,
                "budget_tokens": budget.budget_tokens,
                "used_tokens": budget.used_tokens,
                "remaining": budget.budget_tokens - budget.used_tokens,
                "usage_pct": round(budget.used_tokens / budget.budget_tokens * 100, 1) if budget.budget_tokens > 0 else 0,
                "alert_sent": budget.alert_sent,
            }
        finally:
            db.close()

    def get_or_create_daily(self, day: Optional[str] = None) -> dict:
        day = day or date.today().isoformat()
        db = SessionLocal()
        try:
            budget = db.query(TokenBudget).filter(
                TokenBudget.period == day,
                TokenBudget.period_type == "daily",
            ).first()

            if not budget:
                raw = _get_setting("token_budget_daily", "200000")
                daily_budget = int(raw) if raw else 200000
                budget = TokenBudget(
                    period=day,
                    period_type="daily",
                    budget_tokens=daily_budget,
                    used_tokens=0,
                    created_at=datetime.utcnow(),
                )
                db.add(budget)
                db.commit()
                db.refresh(budget)

            return {
                "period": budget.period,
                "budget_tokens": budget.budget_tokens,
                "used_tokens": budget.used_tokens,
                "remaining": budget.budget_tokens - budget.used_tokens,
                "usage_pct": round(budget.used_tokens / budget.budget_tokens * 100, 1) if budget.budget_tokens > 0 else 0,
            }
        finally:
            db.close()

    def record_usage(self, tokens: int):
        """Record token usage to both daily and monthly budgets."""
        today_str = date.today().isoformat()
        month_str = date.today().strftime("%Y-%m")
        db = SessionLocal()
        try:
            for period, ptype in [(today_str, "daily"), (month_str, "monthly")]:
                budget = db.query(TokenBudget).filter(
                    TokenBudget.period == period,
                    TokenBudget.period_type == ptype,
                ).first()
                if budget:
                    budget.used_tokens += tokens
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record budget usage: {e}")
            db.rollback()
        finally:
            db.close()

    def check_budget_alerts(self) -> list[str]:
        """Check monthly budget and send alerts at 80% threshold. Returns list of alert messages."""
        alerts = []
        month_str = date.today().strftime("%Y-%m")
        db = SessionLocal()
        try:
            budget = db.query(TokenBudget).filter(
                TokenBudget.period == month_str,
                TokenBudget.period_type == "monthly",
            ).first()
            if not budget or budget.budget_tokens <= 0:
                return alerts

            pct = budget.used_tokens / budget.budget_tokens * 100
            if pct >= 80 and not budget.alert_sent:
                msg = f"⚠️ Token 月预算已使用 {pct:.0f}% ({budget.used_tokens:,}/{budget.budget_tokens:,})"
                budget.alert_sent = 1
                db.commit()
                alerts.append(msg)

                try:
                    from harness.feishu_client import feishu_client
                    boss_id = _get_setting("feishu_boss_id")
                    if boss_id:
                        feishu_client.send_text_message(boss_id, msg)
                except Exception:
                    pass

            return alerts
        finally:
            db.close()

    def should_degrade_model(self) -> bool:
        """Check if we should use cheaper model due to budget exhaustion."""
        info = self.get_or_create_monthly()
        return info["usage_pct"] >= 90

    def get_usage_summary(self, days: int = 30) -> dict:
        """Get usage breakdown by model and skill."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        db = SessionLocal()
        try:
            records = db.query(TokenUsage).filter(TokenUsage.created_at >= cutoff).all()
            by_model: dict[str, int] = {}
            by_endpoint: dict[str, int] = {}
            total = 0
            for r in records:
                by_model[r.model] = by_model.get(r.model, 0) + r.total_tokens
                by_endpoint[r.endpoint] = by_endpoint.get(r.endpoint, 0) + r.total_tokens
                total += r.total_tokens

            return {
                "total_tokens": total,
                "record_count": len(records),
                "by_model": by_model,
                "by_endpoint": by_endpoint,
                "days": days,
            }
        finally:
            db.close()


token_budget_manager = TokenBudgetManager()
