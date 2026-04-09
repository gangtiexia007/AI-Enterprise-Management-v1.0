"""F18: KPI Engine — define KPIs, score employees, generate improvement suggestions.

Data source map fields per KPI definition:
  source_type, source_detail, responsible_role,
  update_frequency, dispute_resolver, confidence_baseline

``auto_score_system_kpis`` computes scores for definitions with ``source_type == system``
(e.g. 日报提交率, Sprint 完成率) and upserts ``kpi_scores`` rows.
"""

from __future__ import annotations

import calendar
import json
import logging
from datetime import datetime
from typing import Any

from app.core.database import Database, new_id
from app.core.enums import KPIScoreStatus
from app.core.exceptions import ResourceNotFound, ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

# Approximate working days per month for 日报提交率 denominator
_DEFAULT_WORKING_DAYS = 22


def _month_period_bounds(period_key: str) -> tuple[str, str]:
    """Return [start, end_exclusive) ISO date strings for a YYYY-MM period key."""
    year_s, month_s = period_key.split("-", 1)
    y, m = int(year_s), int(month_s)
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end_excl = f"{y + 1:04d}-01-01"
    else:
        end_excl = f"{y:04d}-{m + 1:02d}-01"
    return start, end_excl


def _working_days_in_month(period_key: str) -> int:
    y, m = map(int, period_key.split("-", 1))
    count = 0
    for d in range(1, calendar.monthrange(y, m)[1] + 1):
        if calendar.weekday(y, m, d) < 5:
            count += 1
    return count or _DEFAULT_WORKING_DAYS


def _determine_grade(kpi: dict[str, Any], pct: float) -> str:
    """Map achievement percentage to a grade using ``scoring_json`` or defaults."""
    scoring = kpi.get("scoring_json", "{}")
    if isinstance(scoring, str):
        try:
            scoring = json.loads(scoring or "{}")
        except (json.JSONDecodeError, TypeError):
            scoring = {}
    if not isinstance(scoring, dict):
        scoring = {}

    bands = scoring.get("grade_bands") or scoring.get("bands")
    if isinstance(bands, list) and bands:
        try:
            ordered = sorted(
                (b for b in bands if isinstance(b, dict)),
                key=lambda x: float(x.get("min_pct", x.get("min", 0))),
                reverse=True,
            )
            for b in ordered:
                threshold = float(b.get("min_pct", b.get("min", 0)))
                if pct >= threshold:
                    return str(b.get("grade", "C"))
        except (TypeError, ValueError):
            pass

    if pct >= 95:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 60:
        return "C"
    return "D"


def _calculate_system_metric(
    db: Database,
    kpi: dict[str, Any],
    employee: dict[str, Any],
    period_key: str,
) -> float | None:
    """Actual value for system-type KPIs (returns None to skip this employee)."""
    name = (kpi.get("name") or "").lower()
    emp_id = employee["id"]
    team_id = kpi["team_id"]
    start, end_excl = _month_period_bounds(period_key)

    if "完成率" in name or "sprint" in name:
        total_rows = db.execute(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE team_id=? AND employee_id=? "
            "AND created_at >= ? AND created_at < ?",
            (team_id, emp_id, start, end_excl),
        )
        total = int(total_rows[0]["cnt"]) if total_rows else 0
        if total <= 0:
            return None
        done_rows = db.execute(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE team_id=? AND employee_id=? "
            "AND created_at >= ? AND created_at < ? "
            "AND status IN ('completed','scored')",
            (team_id, emp_id, start, end_excl),
        )
        done = int(done_rows[0]["cnt"]) if done_rows else 0
        return round(done / total * 100, 4)

    if "提交率" in name or "日报" in name:
        fb_rows = db.execute(
            "SELECT COUNT(*) AS cnt FROM task_feedbacks WHERE employee_id=? "
            "AND submitted_at >= ? AND submitted_at < ?",
            (emp_id, start, end_excl),
        )
        feedbacks = int(fb_rows[0]["cnt"]) if fb_rows else 0
        days = _working_days_in_month(period_key)
        if days <= 0:
            days = _DEFAULT_WORKING_DAYS
        return round(min(100.0, feedbacks / days * 100), 4)

    return None


def auto_score_system_kpis(
    team_ids: list[str] | None = None,
    period_key: str | None = None,
) -> int:
    """Score all system KPI definitions; upsert ``kpi_scores``. Returns rows written."""
    db = Database.get_instance()
    if not period_key:
        period_key = datetime.utcnow().strftime("%Y-%m")

    if team_ids:
        placeholders = ",".join(["?"] * len(team_ids))
        kpi_defs = db.execute(
            f"SELECT * FROM kpi_definitions WHERE source_type=? "
            f"AND team_id IN ({placeholders}) LIMIT 500",
            ("system", *team_ids),
        )
    else:
        kpi_defs = db.execute(
            "SELECT * FROM kpi_definitions WHERE source_type=? LIMIT 500",
            ("system",),
        )

    scored_count = 0
    now = datetime.utcnow().isoformat()

    for kpi in kpi_defs:
        team_id = kpi["team_id"]
        employees = db.query("employees", {"team_id": team_id}, limit=500)

        for emp in employees:
            actual_value = _calculate_system_metric(db, kpi, emp, period_key)
            if actual_value is None:
                continue

            target = float(kpi.get("target_value") or 0)
            if target > 0:
                pct = actual_value / target * 100
            else:
                pct = 0.0

            grade = _determine_grade(kpi, pct)

            existing = db.execute(
                "SELECT id FROM kpi_scores WHERE kpi_def_id=? AND employee_id=? "
                "AND period_key=?",
                (kpi["id"], emp["id"], period_key),
            )

            scores_json = {
                "auto": True,
                "actual_value": actual_value,
                "target": target,
                "achievement_pct": round(pct, 4),
                "kpi_name": kpi.get("name", ""),
            }
            score_data: dict[str, Any] = {
                "kpi_def_id": kpi["id"],
                "employee_id": emp["id"],
                "period_key": period_key,
                "scores_json": scores_json,
                "total_score": round(pct, 2),
                "grade": grade,
                "status": "auto",
                "feedback": (
                    f"系统自动评分: 实际值={actual_value}, 目标={target}"
                ),
                "scored_at": now,
            }

            if existing:
                db.update("kpi_scores", existing[0]["id"], score_data)
            else:
                score_data["id"] = new_id()
                db.insert("kpi_scores", score_data)
            scored_count += 1

    if scored_count:
        logger.info(
            "auto_score_system_kpis: period=%s rows=%d", period_key, scored_count
        )
    return scored_count


class KPIEngine(EngineBase):
    """Manages KPI definitions, calculates scores, and generates feedback."""

    def create_kpi_definition(
        self,
        team_id: str,
        name: str,
        period: str = "monthly",
        metrics: dict[str, Any] | None = None,
        scoring: dict[str, Any] | None = None,
        target: float = 0.0,
        weight: float = 1.0,
        data_source_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not team_id or not name:
            raise ValidationError("team_id and name are required")

        dsm = data_source_map or {}

        kpi = {
            "id": new_id(),
            "team_id": team_id,
            "name": name,
            "period": period,
            "metrics_json": metrics or {},
            "scoring_json": scoring or {},
            "weight": weight,
            "target_value": target,
            "source_type": dsm.get("source_type", ""),
            "source_detail": dsm.get("source_detail", ""),
            "responsible_role": dsm.get("responsible_role", ""),
            "update_frequency": dsm.get("update_frequency", ""),
            "dispute_resolver": dsm.get("dispute_resolver", ""),
            "confidence_baseline": dsm.get("confidence_baseline", ""),
            "created_at": self._now_iso(),
        }
        self._insert("kpi_definitions", kpi)
        logger.info("KPI definition created: %s '%s'", kpi["id"], name)
        return kpi

    def score_employee(
        self, employee_id: str, period_key: str
    ) -> dict[str, Any]:
        """Calculate aggregate KPI score for an employee in a given period.

        For each KPI definition assigned to the employee's team, look up the
        scoring_json formula and compute a weighted total.
        """
        emp = self._get_by_id("employees", employee_id)
        team_id = emp.get("team_id", "")

        kpi_defs = self._query("kpi_definitions", {"team_id": team_id})
        if not kpi_defs:
            raise ValidationError(f"No KPI definitions found for team {team_id}")

        scores: dict[str, Any] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for kd in kpi_defs:
            kd_id = kd["id"]
            weight = float(kd.get("weight", 1.0))
            scoring_json = self._parse_json_field(kd.get("scoring_json", "{}"))
            target_value = float(kd.get("target_value", 0))

            raw_score = self._compute_kpi_score(
                kd_id, employee_id, period_key, scoring_json, target_value
            )
            scores[kd["name"]] = {
                "kpi_def_id": kd_id,
                "raw_score": raw_score,
                "weight": weight,
                "weighted_score": round(raw_score * weight, 2),
            }
            weighted_sum += raw_score * weight
            total_weight += weight

        total_score = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0
        grade = self._score_to_grade(total_score)

        kpi_score = {
            "id": new_id(),
            "kpi_def_id": kpi_defs[0]["id"] if kpi_defs else "",
            "employee_id": employee_id,
            "period_key": period_key,
            "scores_json": scores,
            "total_score": total_score,
            "grade": grade,
            "feedback": "",
            "status": KPIScoreStatus.CALCULATED.value,
            "scored_at": self._now_iso(),
        }
        self._insert("kpi_scores", kpi_score)
        logger.info(
            "KPI scored: employee=%s period=%s total=%.2f grade=%s",
            employee_id, period_key, total_score, grade,
        )
        return kpi_score

    def _compute_kpi_score(
        self,
        kpi_def_id: str,
        employee_id: str,
        period_key: str,
        scoring_json: dict[str, Any],
        target_value: float,
    ) -> float:
        """Compute a single KPI dimension score.

        Supported formula types in scoring_json:
          - {"type": "task_completion_rate"}: ratio of completed tasks
          - {"type": "fixed", "value": <float>}: fixed score
          - default: returns 75.0 placeholder
        """
        formula_type = scoring_json.get("type", "default")

        if formula_type == "task_completion_rate":
            return self._calc_task_completion_rate(employee_id, period_key)

        if formula_type == "fixed":
            return float(scoring_json.get("value", 75.0))

        return 75.0

    def _calc_task_completion_rate(self, employee_id: str, period_key: str) -> float:
        period_start = f"{period_key}-01" if len(period_key) == 7 else period_key
        all_tasks = self._execute(
            "SELECT status FROM tasks WHERE employee_id=? AND created_at >= ?",
            (employee_id, period_start),
        )
        if not all_tasks:
            return 0.0
        completed = sum(1 for t in all_tasks if t["status"] == "completed")
        return round(completed / len(all_tasks) * 100, 2)

    def generate_improvement_suggestion(
        self, employee_id: str, kpi_score: dict[str, Any]
    ) -> str:
        """Generate LLM-based improvement advice. Placeholder for V1."""
        grade = kpi_score.get("grade", "C")
        total = kpi_score.get("total_score", 0)
        scores_detail = self._parse_json_field(kpi_score.get("scores_json", "{}"))

        weak_areas: list[str] = []
        if isinstance(scores_detail, dict):
            for name, detail in scores_detail.items():
                if isinstance(detail, dict) and detail.get("raw_score", 100) < 70:
                    weak_areas.append(name)

        if not weak_areas:
            return f"当前综合评分 {total}（{grade}级），表现良好，请保持。"

        areas_str = "、".join(weak_areas)
        return (
            f"当前综合评分 {total}（{grade}级）。"
            f"建议重点关注以下薄弱指标：{areas_str}。"
            f"可参考团队内高绩效同事的做法，制定针对性改进计划。"
        )

    def list_kpi_definitions(self, team_id: str) -> list[dict[str, Any]]:
        return self._query("kpi_definitions", {"team_id": team_id})

    def get_score_history(
        self, employee_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        return self._query(
            "kpi_scores",
            {"employee_id": employee_id},
            order_by="scored_at DESC",
            limit=limit,
        )

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"
