"""F34: Report Generator — daily, weekly, and monthly reports.

Daily morning report includes:
  - Pending approvals
  - Yesterday's anomalies (overdue tasks, escalations)
  - Today's tasks
  - Risk warnings

Weekly and monthly reports add goal progress and decision tracking.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from app.core.database import new_id
from app.core.enums import ReportType, TaskStatus
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)


class ReportGenerator(EngineBase):
    """Generates structured reports for teams."""

    def generate_daily_report(self, team_id: str) -> dict[str, Any]:
        today = date.today()
        yesterday = today - timedelta(days=1)

        pending_approvals = self._get_pending_approvals(team_id)
        yesterday_anomalies = self._get_anomalies(team_id, yesterday.isoformat())
        today_tasks = self._get_today_tasks(team_id, today.isoformat())
        risk_warnings = self._get_risk_warnings(team_id)

        stats = {
            "pending_approvals": pending_approvals,
            "yesterday_anomalies": yesterday_anomalies,
            "today_tasks": today_tasks,
            "risk_warnings": risk_warnings,
        }

        team = self._get_by_id_optional("teams", team_id) or {}
        summary = self._generate_summary(team, stats, "日报")

        report = {
            "id": new_id(),
            "team_id": team_id,
            "date": today.isoformat(),
            "report_type": ReportType.DAILY.value,
            "summary": summary,
            "stats_json": stats,
            "knowledge_candidates_json": [],
            "created_at": self._now_iso(),
        }
        self._insert("dream_reports", report)
        self._try_push_report(report["id"])
        logger.info("Daily report generated for team %s", team_id)
        return report

    def generate_weekly_report(self, team_id: str) -> dict[str, Any]:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        task_stats = self._get_task_stats(team_id, week_start.isoformat(), today.isoformat())
        goal_progress = self._get_goal_progress(team_id)
        escalation_summary = self._get_escalation_summary(team_id, week_start.isoformat())

        stats = {
            "period": f"{week_start.isoformat()} ~ {today.isoformat()}",
            "task_stats": task_stats,
            "goal_progress": goal_progress,
            "escalation_summary": escalation_summary,
        }

        team = self._get_by_id_optional("teams", team_id) or {}
        summary = self._generate_summary(team, stats, "周报")

        report = {
            "id": new_id(),
            "team_id": team_id,
            "date": today.isoformat(),
            "report_type": ReportType.WEEKLY.value,
            "summary": summary,
            "stats_json": stats,
            "knowledge_candidates_json": [],
            "created_at": self._now_iso(),
        }
        self._insert("dream_reports", report)
        self._try_push_report(report["id"])
        logger.info("Weekly report generated for team %s", team_id)
        return report

    def generate_monthly_report(self, team_id: str) -> dict[str, Any]:
        today = date.today()
        month_start = today.replace(day=1)

        task_stats = self._get_task_stats(team_id, month_start.isoformat(), today.isoformat())
        goal_progress = self._get_goal_progress(team_id)
        decision_summary = self._get_decision_summary(team_id, month_start.isoformat())
        kpi_summary = self._get_kpi_summary(team_id)

        stats = {
            "period": f"{month_start.isoformat()} ~ {today.isoformat()}",
            "task_stats": task_stats,
            "goal_progress": goal_progress,
            "decision_summary": decision_summary,
            "kpi_summary": kpi_summary,
        }

        team = self._get_by_id_optional("teams", team_id) or {}
        summary = self._generate_summary(team, stats, "月报")

        report = {
            "id": new_id(),
            "team_id": team_id,
            "date": today.isoformat(),
            "report_type": ReportType.MONTHLY.value,
            "summary": summary,
            "stats_json": stats,
            "knowledge_candidates_json": [],
            "created_at": self._now_iso(),
        }
        self._insert("dream_reports", report)
        self._try_push_report(report["id"])
        logger.info("Monthly report generated for team %s", team_id)
        return report

    def _generate_summary(
        self, team: dict[str, Any], stats: dict[str, Any], period_type: str
    ) -> str:
        """Generate a natural language summary using LLM, with stat-based fallback."""
        stats_text = json.dumps(stats, ensure_ascii=False, indent=2)
        team_label = team.get("display_name") or team.get("name", "")

        prompt = f"""你是{team_label}团队的AI助手。请根据以下数据生成一份简洁的{period_type}工作总结。

数据:
{stats_text}

要求:
1. 用2-3段话总结关键情况
2. 指出突出成绩和需要关注的问题
3. 给出1-2条建议
4. 语言简洁专业"""

        try:
            from app.runtime.llm import LLMClient
            from app.runtime.model_router import ModelRouter

            router = ModelRouter.get_instance()
            model_name = router.select_cheap_model()
            api_key = router.decrypt_api_key_for_model(model_name) or ""
            kwargs: dict[str, Any] = {}
            if api_key:
                kwargs["api_key"] = api_key

            async def _call() -> str:
                client = LLMClient()
                resp = await client.complete(
                    model_name,
                    [{"role": "user", "content": prompt}],
                    temperature=0.4,
                    max_tokens=800,
                    **kwargs,
                )
                return (resp.content or "").strip()

            try:
                text = asyncio.run(_call())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    text = loop.run_until_complete(_call())
                finally:
                    loop.close()

            if text:
                return text
            return f"统计数据: {stats_text[:300]}"
        except Exception as exc:
            logger.warning("LLM summary failed: %s", exc)
            return self._fallback_summary_text(stats, period_type)

    def _fallback_summary_text(
        self, stats: dict[str, Any], period_type: str
    ) -> str:
        """Short non-LLM summary when the model is unavailable."""
        if period_type == "日报":
            return (
                f"数据统计（{period_type}）：待审批 {len(stats.get('pending_approvals', []))} 项，"
                f"昨日异常 {len(stats.get('yesterday_anomalies', []))} 项，"
                f"今日任务 {len(stats.get('today_tasks', []))} 项，"
                f"风险预警 {len(stats.get('risk_warnings', []))} 项。"
            )
        if period_type == "周报":
            ts = stats.get("task_stats") or {}
            esc = stats.get("escalation_summary") or {}
            return (
                f"数据统计（{period_type}）：任务完成 {ts.get('completed', 0)}/"
                f"{ts.get('total', 0)}，预警 {esc.get('count', 0)} 次。"
            )
        ts = stats.get("task_stats") or {}
        kpi = stats.get("kpi_summary") or {}
        dec = stats.get("decision_summary") or {}
        return (
            f"数据统计（{period_type}）：任务完成 {ts.get('completed', 0)}/"
            f"{ts.get('total', 0)}，KPI 均分 {kpi.get('avg_score', 0):.1f}，"
            f"决策记录 {dec.get('count', 0)} 条。"
        )

    def _try_push_report(self, report_id: str) -> None:
        try:
            from app.dream.push import push_report_sync

            push_report_sync(report_id)
        except Exception:
            logger.debug("Dream report push skipped or failed", exc_info=True)

    # ── Data collection helpers ───────────────────────────────────

    def _get_pending_approvals(self, team_id: str) -> list[dict[str, Any]]:
        return self._query("approval_requests", {
            "team_id": team_id, "status": "pending",
        }, limit=50)

    def _get_anomalies(self, team_id: str, date_str: str) -> list[dict[str, Any]]:
        anomalies: list[dict[str, Any]] = []

        overdue = self._execute(
            "SELECT id, title, deadline_at FROM tasks "
            "WHERE team_id=? AND deadline_at < ? AND status NOT IN ('completed','scored')",
            (team_id, f"{date_str}T23:59:59"),
        )
        for t in overdue:
            anomalies.append({"type": "overdue_task", "detail": t})

        escalations = self._execute(
            "SELECT * FROM escalations WHERE sent_at >= ? AND sent_at <= ?",
            (f"{date_str}T00:00:00", f"{date_str}T23:59:59"),
        )
        for e in escalations:
            anomalies.append({"type": "escalation", "detail": e})

        return anomalies

    def _get_today_tasks(self, team_id: str, date_str: str) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT * FROM tasks WHERE team_id=? "
            "AND status IN (?, ?, ?) ORDER BY deadline_at ASC",
            (
                team_id,
                TaskStatus.PENDING.value,
                TaskStatus.DISPATCHED.value,
                TaskStatus.IN_PROGRESS.value,
            ),
        )

    def _get_risk_warnings(self, team_id: str) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []

        soon_deadline = (datetime.utcnow() + timedelta(hours=4)).isoformat()
        at_risk = self._execute(
            "SELECT id, title, deadline_at FROM tasks "
            "WHERE team_id=? AND deadline_at <= ? AND status NOT IN (?, ?)",
            (team_id, soon_deadline, TaskStatus.COMPLETED.value, TaskStatus.SCORED.value),
        )
        for t in at_risk:
            warnings.append({"type": "deadline_imminent", "task": t})

        return warnings

    def _get_task_stats(
        self, team_id: str, start: str, end: str
    ) -> dict[str, Any]:
        total = self._execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE team_id=? "
            "AND created_at >= ? AND created_at <= ?",
            (team_id, f"{start}T00:00:00", f"{end}T23:59:59"),
        )
        completed = self._execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE team_id=? "
            "AND status=? AND completed_at >= ? AND completed_at <= ?",
            (team_id, TaskStatus.COMPLETED.value, f"{start}T00:00:00", f"{end}T23:59:59"),
        )
        return {
            "total": total[0]["cnt"] if total else 0,
            "completed": completed[0]["cnt"] if completed else 0,
        }

    def _get_goal_progress(self, team_id: str) -> list[dict[str, Any]]:
        goals = self._query("goals", {"team_id": team_id, "status": "tracking"}, limit=50)
        result = []
        for g in goals:
            target = float(g.get("target_value", 0))
            current = float(g.get("current_value", 0))
            progress = round(current / target * 100, 1) if target > 0 else 0.0
            result.append({
                "goal_id": g["id"],
                "title": g.get("title", ""),
                "progress": progress,
                "current": current,
                "target": target,
            })
        return result

    def _get_escalation_summary(
        self, team_id: str, start: str
    ) -> dict[str, Any]:
        rows = self._execute(
            "SELECT COUNT(*) as cnt FROM escalations e "
            "JOIN tasks t ON t.id = e.task_id "
            "WHERE t.team_id=? AND e.sent_at >= ?",
            (team_id, f"{start}T00:00:00"),
        )
        return {"count": rows[0]["cnt"] if rows else 0}

    def _get_decision_summary(
        self, team_id: str, start: str
    ) -> dict[str, Any]:
        rows = self._execute(
            "SELECT COUNT(*) as cnt FROM decision_logs "
            "WHERE team_id=? AND created_at >= ?",
            (team_id, f"{start}T00:00:00"),
        )
        return {"count": rows[0]["cnt"] if rows else 0}

    def _get_kpi_summary(self, team_id: str) -> dict[str, Any]:
        rows = self._execute(
            "SELECT AVG(ks.total_score) as avg_score, COUNT(*) as cnt "
            "FROM kpi_scores ks "
            "JOIN employees e ON e.id = ks.employee_id "
            "WHERE e.team_id = ?",
            (team_id,),
        )
        if rows and rows[0].get("cnt", 0) > 0:
            return {
                "avg_score": round(rows[0].get("avg_score", 0) or 0, 2),
                "count": rows[0]["cnt"],
            }
        return {"avg_score": 0, "count": 0}
