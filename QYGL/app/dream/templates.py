"""F35: Template Engine — simple string format templates for reports and notifications.

Built-in templates for:
  - daily_report, weekly_report, monthly_report
  - task_notification, escalation_warning, kpi_feedback
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


BUILTIN_TEMPLATES: dict[str, str] = {
    # ── Reports ───────────────────────────────────────────────────
    "daily_report": (
        "📋 {team_name} 每日报告 — {date}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📌 待审批: {pending_count} 项\n"
        "⚠️ 昨日异常: {anomaly_count} 项\n"
        "📝 今日任务: {task_count} 项\n"
        "🔔 风险预警: {risk_count} 项\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "{details}"
    ),
    "weekly_report": (
        "📊 {team_name} 周报 — {period}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "任务完成: {completed}/{total}\n"
        "目标进度: {goal_progress}\n"
        "预警次数: {escalation_count}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "{details}"
    ),
    "monthly_report": (
        "📈 {team_name} 月报 — {period}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "任务完成: {completed}/{total}\n"
        "KPI 均分: {kpi_avg}\n"
        "决策记录: {decision_count} 条\n"
        "目标进度: {goal_progress}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "{details}"
    ),

    # ── Notifications ─────────────────────────────────────────────
    "task_notification": (
        "📌 新任务提醒\n"
        "任务: {title}\n"
        "描述: {description}\n"
        "截止: {deadline}\n"
        "负责人: {employee_name}"
    ),
    "escalation_warning": (
        "🚨 {level}级预警\n"
        "任务「{task_title}」已逾期 {hours_overdue} 小时\n"
        "当前状态: {status}\n"
        "请及时处理。"
    ),
    "kpi_feedback": (
        "📊 KPI 评分通知\n"
        "周期: {period}\n"
        "综合评分: {total_score}（{grade}级）\n"
        "{dimension_details}\n"
        "改进建议: {suggestion}"
    ),

    # ── Customer ──────────────────────────────────────────────────
    "customer_churn_warning": (
        "⚠️ 客户流失预警\n"
        "客户: {customer_name}（{company}）\n"
        "最近联系: {last_contact_days} 天前\n"
        "负责人: {employee_name}\n"
        "请尽快跟进。"
    ),

    # ── Approval ──────────────────────────────────────────────────
    "approval_request": (
        "📋 审批请求\n"
        "类型: {approval_type}\n"
        "标题: {title}\n"
        "详情: {detail}\n"
        "建议: {suggestion}"
    ),
}


class TemplateEngine:
    """Renders built-in templates or custom templates with variable substitution."""

    def __init__(self, custom_templates: dict[str, str] | None = None):
        self.templates: dict[str, str] = dict(BUILTIN_TEMPLATES)
        if custom_templates:
            self.templates.update(custom_templates)

    def render_template(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """Render a named template with the given variables.

        Missing variables are replaced with empty strings rather than raising.
        """
        template = self.templates.get(template_name)
        if template is None:
            logger.warning("Template '%s' not found, returning raw name", template_name)
            return template_name

        safe_vars = _SafeDict(variables or {})
        try:
            return template.format_map(safe_vars)
        except Exception:
            logger.error("Failed to render template '%s'", template_name, exc_info=True)
            return template

    def list_templates(self) -> list[str]:
        return sorted(self.templates.keys())

    def register_template(self, name: str, template: str) -> None:
        self.templates[name] = template

    def get_raw_template(self, name: str) -> str | None:
        return self.templates.get(name)


class _SafeDict(dict):
    """Dict subclass that returns '{key}' for missing keys in str.format_map."""

    def __missing__(self, key: str) -> str:
        return ""
