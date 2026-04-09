"""F41: Decision Logger — record, track, and review business decisions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.database import new_id
from app.core.enums import ReviewStatus
from app.core.exceptions import ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)


class DecisionEngine(EngineBase):
    """Records decisions with data basis and tracks outcomes for monthly review."""

    def record_decision(
        self,
        team_id: str,
        employee_id: str,
        decision: str,
        data_basis: str = "",
        expected_result: str = "",
    ) -> dict[str, Any]:
        if not decision:
            raise ValidationError("decision text is required")

        record = {
            "id": new_id(),
            "team_id": team_id,
            "employee_id": employee_id,
            "decision": decision,
            "data_basis": data_basis,
            "expected_result": expected_result,
            "actual_result": "",
            "evaluation": "",
            "tracked_metrics_json": {},
            "metric_snapshot_before": {},
            "metric_snapshot_after": {},
            "review_status": ReviewStatus.PENDING.value,
            "review_result": "",
            "created_at": self._now_iso(),
        }
        self._insert("decision_logs", record)
        logger.info("Decision recorded: %s by employee %s", record["id"], employee_id)
        return record

    def track_metrics(self, decision_id: str) -> dict[str, Any]:
        """Snapshot current metrics at the time of decision for later comparison."""
        decision = self._get_by_id("decision_logs", decision_id)
        team_id = decision.get("team_id", "")
        employee_id = decision.get("employee_id", "")

        snapshot = self._collect_metric_snapshot(team_id, employee_id)

        existing_before = self._parse_json_field(
            decision.get("metric_snapshot_before", "{}")
        )
        if not existing_before or (isinstance(existing_before, dict) and not existing_before):
            self._update("decision_logs", decision_id, {
                "metric_snapshot_before": snapshot,
            })
            logger.info("Before-snapshot captured for decision %s", decision_id)
        else:
            self._update("decision_logs", decision_id, {
                "metric_snapshot_after": snapshot,
            })
            logger.info("After-snapshot captured for decision %s", decision_id)

        return snapshot

    def review_decision(self, decision_id: str) -> dict[str, Any]:
        """Compare before/after metrics and generate an evaluation."""
        decision = self._get_by_id("decision_logs", decision_id)

        before = self._parse_json_field(decision.get("metric_snapshot_before", "{}"))
        after_snapshot = self._collect_metric_snapshot(
            decision.get("team_id", ""), decision.get("employee_id", "")
        )

        self._update("decision_logs", decision_id, {
            "metric_snapshot_after": after_snapshot,
        })

        evaluation = self._compare_snapshots(before, after_snapshot, decision)
        actual_result = evaluation.get("summary", "")

        self._update("decision_logs", decision_id, {
            "actual_result": actual_result,
            "evaluation": json.dumps(evaluation, ensure_ascii=False),
            "review_status": ReviewStatus.REVIEWED.value,
        })

        logger.info("Decision reviewed: %s", decision_id)
        return {
            "decision_id": decision_id,
            "before": before,
            "after": after_snapshot,
            "evaluation": evaluation,
        }

    def generate_review_report(
        self, team_id: str, period: str = ""
    ) -> dict[str, Any]:
        """Generate a monthly decision review report."""
        if not period:
            now = datetime.utcnow()
            period = now.strftime("%Y-%m")

        start = f"{period}-01T00:00:00"
        month_num = int(period.split("-")[1])
        year_num = int(period.split("-")[0])
        if month_num == 12:
            end = f"{year_num + 1}-01-01T00:00:00"
        else:
            end = f"{year_num}-{month_num + 1:02d}-01T00:00:00"

        decisions = self._execute(
            "SELECT * FROM decision_logs "
            "WHERE team_id=? AND created_at >= ? AND created_at < ? "
            "ORDER BY created_at ASC",
            (team_id, start, end),
        )

        reviewed = [d for d in decisions if d.get("review_status") == ReviewStatus.REVIEWED.value]
        pending = [d for d in decisions if d.get("review_status") == ReviewStatus.PENDING.value]

        report = {
            "period": period,
            "team_id": team_id,
            "total_decisions": len(decisions),
            "reviewed_count": len(reviewed),
            "pending_count": len(pending),
            "decisions": [
                {
                    "id": d["id"],
                    "decision": d.get("decision", ""),
                    "expected_result": d.get("expected_result", ""),
                    "actual_result": d.get("actual_result", ""),
                    "review_status": d.get("review_status", ""),
                }
                for d in decisions
            ],
        }

        logger.info(
            "Decision review report for team=%s period=%s: %d decisions",
            team_id, period, len(decisions),
        )
        return report

    # ── Internal helpers ──────────────────────────────────────────

    def _collect_metric_snapshot(
        self, team_id: str, employee_id: str
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {"timestamp": self._now_iso()}

        task_rows = self._execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed "
            "FROM tasks WHERE team_id=?",
            (team_id,),
        )
        if task_rows:
            snapshot["task_total"] = task_rows[0].get("total", 0)
            snapshot["task_completed"] = task_rows[0].get("completed", 0)

        kpi_rows = self._execute(
            "SELECT AVG(total_score) as avg_score FROM kpi_scores "
            "WHERE employee_id=?",
            (employee_id,),
        )
        if kpi_rows and kpi_rows[0].get("avg_score") is not None:
            snapshot["kpi_avg"] = round(float(kpi_rows[0]["avg_score"]), 2)

        return snapshot

    def _compare_snapshots(
        self,
        before: Any,
        after: Any,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(before, dict) or not isinstance(after, dict):
            return {"summary": "指标快照不完整，无法比较。", "changes": {}}

        changes: dict[str, Any] = {}
        for key in ("task_completed", "task_total", "kpi_avg"):
            bv = before.get(key, 0)
            av = after.get(key, 0)
            if bv or av:
                try:
                    changes[key] = {
                        "before": float(bv) if bv else 0,
                        "after": float(av) if av else 0,
                        "delta": round(float(av or 0) - float(bv or 0), 2),
                    }
                except (ValueError, TypeError):
                    pass

        expected = decision.get("expected_result", "")
        if not changes:
            summary = "暂无明显指标变化。"
        else:
            parts = []
            for k, v in changes.items():
                direction = "↑" if v["delta"] > 0 else ("↓" if v["delta"] < 0 else "→")
                parts.append(f"{k}: {v['before']} {direction} {v['after']}")
            summary = "指标变化: " + "; ".join(parts)

        return {"summary": summary, "changes": changes, "expected": expected}
