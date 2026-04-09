"""F33: Knowledge Extractor — find good patterns from high-performing tasks and KPIs.

Extracts knowledge candidates from:
- Tasks with score >= 90 (A-grade)
- Recurring successful patterns in task feedback
Creates knowledge entries with status="candidate" pending human review.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.database import new_id
from app.core.enums import KnowledgeScope, KnowledgeSource, KnowledgeStatus
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

HIGH_SCORE_THRESHOLD = 90.0
FEEDBACK_MIN_LEN = 80


class KnowledgeExtractor(EngineBase):
    """Mines high-quality task completions for reusable knowledge."""

    def extract_knowledge_candidates(
        self, team_id: str
    ) -> list[dict[str, Any]]:
        """Scan recent high-scoring tasks and create knowledge candidate entries."""
        candidates: list[dict[str, Any]] = []

        task_candidates = self._extract_from_tasks(team_id)
        candidates.extend(task_candidates)

        kpi_candidates = self._extract_from_kpi_scores(team_id)
        candidates.extend(kpi_candidates)

        feedback_candidates = self._extract_from_rich_feedbacks(team_id)
        candidates.extend(feedback_candidates)

        decision_candidates = self._extract_from_reviewed_decisions(team_id)
        candidates.extend(decision_candidates)

        logger.info(
            "Extracted %d knowledge candidates for team %s",
            len(candidates), team_id,
        )
        return candidates

    def _extract_from_tasks(self, team_id: str) -> list[dict[str, Any]]:
        high_tasks = self._execute(
            "SELECT * FROM tasks WHERE team_id=? AND score >= ? "
            "AND status = 'completed' ORDER BY score DESC LIMIT 50",
            (team_id, HIGH_SCORE_THRESHOLD),
        )

        candidates: list[dict[str, Any]] = []
        for task in high_tasks:
            existing = self._query("knowledge", {
                "category": f"task_{task['id']}",
                "status": KnowledgeStatus.CANDIDATE.value,
            })
            if existing:
                continue

            feedbacks = self._query(
                "task_feedbacks", {"task_id": task["id"]}, limit=10
            )
            feedback_text = "\n".join(
                fb.get("content", "") for fb in feedbacks if fb.get("content")
            )

            content = self._build_task_knowledge(task, feedback_text)
            knowledge = {
                "id": new_id(),
                "title": f"优秀实践 — {task.get('title', '未知任务')}",
                "content": content,
                "scope": KnowledgeScope.DEPARTMENT.value,
                "department": "",
                "category": f"task_{task['id']}",
                "source": KnowledgeSource.DREAM.value,
                "status": KnowledgeStatus.CANDIDATE.value,
                "created_by": "dream_extractor",
                "created_at": self._now_iso(),
            }
            self._insert("knowledge", knowledge)
            candidates.append(knowledge)

        return candidates

    def _extract_from_kpi_scores(self, team_id: str) -> list[dict[str, Any]]:
        top_scores = self._execute(
            "SELECT ks.* FROM kpi_scores ks "
            "JOIN employees e ON e.id = ks.employee_id "
            "WHERE e.team_id = ? AND ks.grade = 'A' "
            "ORDER BY ks.total_score DESC LIMIT 20",
            (team_id,),
        )

        candidates: list[dict[str, Any]] = []
        for score_row in top_scores:
            existing = self._query("knowledge", {
                "category": f"kpi_{score_row['id']}",
                "status": KnowledgeStatus.CANDIDATE.value,
            })
            if existing:
                continue

            scores_detail = self._parse_json_field(
                score_row.get("scores_json", "{}")
            )
            content = self._build_kpi_knowledge(score_row, scores_detail)

            knowledge = {
                "id": new_id(),
                "title": f"高绩效模式 — 员工 {score_row.get('employee_id', '?')} "
                         f"({score_row.get('period_key', '')})",
                "content": content,
                "scope": KnowledgeScope.DEPARTMENT.value,
                "category": f"kpi_{score_row['id']}",
                "source": KnowledgeSource.DREAM.value,
                "status": KnowledgeStatus.CANDIDATE.value,
                "created_by": "dream_extractor",
                "created_at": self._now_iso(),
            }
            self._insert("knowledge", knowledge)
            candidates.append(knowledge)

        return candidates

    def _extract_from_rich_feedbacks(self, team_id: str) -> list[dict[str, Any]]:
        rows = self._execute(
            "SELECT tf.*, t.title AS task_title FROM task_feedbacks tf "
            "JOIN tasks t ON t.id = tf.task_id "
            "WHERE t.team_id = ? AND tf.feedback_type = 'text' "
            "AND length(trim(tf.content)) >= ? "
            "ORDER BY tf.submitted_at DESC LIMIT 40",
            (team_id, FEEDBACK_MIN_LEN),
        )
        candidates: list[dict[str, Any]] = []
        for row in rows:
            cat = f"task_feedback_{row['id']}"
            existing = self._query(
                "knowledge",
                {"category": cat, "status": KnowledgeStatus.CANDIDATE.value},
            )
            if existing:
                continue

            content = self._build_feedback_knowledge(row)
            knowledge = {
                "id": new_id(),
                "title": f"高质量反馈 — {row.get('task_title', '任务')}",
                "content": content,
                "scope": KnowledgeScope.DEPARTMENT.value,
                "department": "",
                "category": cat,
                "source": KnowledgeSource.DREAM.value,
                "status": KnowledgeStatus.CANDIDATE.value,
                "created_by": "dream_extractor",
                "created_at": self._now_iso(),
            }
            self._insert("knowledge", knowledge)
            candidates.append(knowledge)

        return candidates

    def _extract_from_reviewed_decisions(self, team_id: str) -> list[dict[str, Any]]:
        rows = self._execute(
            "SELECT * FROM decision_logs "
            "WHERE team_id = ? AND review_status = 'reviewed' "
            "ORDER BY created_at DESC LIMIT 40",
            (team_id,),
        )
        candidates: list[dict[str, Any]] = []
        for row in rows:
            cat = f"decision_{row['id']}"
            existing = self._query(
                "knowledge",
                {"category": cat, "status": KnowledgeStatus.CANDIDATE.value},
            )
            if existing:
                continue

            content = self._build_decision_knowledge(row)
            title_hint = (row.get("decision") or "")[:48]
            knowledge = {
                "id": new_id(),
                "title": f"已复盘决策 — {title_hint}",
                "content": content,
                "scope": KnowledgeScope.DEPARTMENT.value,
                "department": "",
                "category": cat,
                "source": KnowledgeSource.DREAM.value,
                "status": KnowledgeStatus.CANDIDATE.value,
                "created_by": "dream_extractor",
                "created_at": self._now_iso(),
            }
            self._insert("knowledge", knowledge)
            candidates.append(knowledge)

        return candidates

    def _build_feedback_knowledge(self, row: dict[str, Any]) -> str:
        lines = [
            "来源: 任务文字反馈（高质量）",
            f"任务: {row.get('task_title', '')}",
            f"提交时间: {row.get('submitted_at', '')}",
            f"内容:\n{row.get('content', '')[:2000]}",
        ]
        return "\n".join(lines)

    def _build_decision_knowledge(self, row: dict[str, Any]) -> str:
        lines = [
            "来源: 已复盘决策记录",
            f"决策: {row.get('decision', '')}",
            f"依据: {row.get('data_basis', '')}",
            f"预期结果: {row.get('expected_result', '')}",
            f"实际结果: {row.get('actual_result', '')}",
            f"复盘评价: {row.get('review_result', '') or row.get('evaluation', '')}",
        ]
        return "\n".join(lines)

    def _build_task_knowledge(
        self, task: dict[str, Any], feedback_text: str
    ) -> str:
        lines = [
            f"任务: {task.get('title', '')}",
            f"描述: {task.get('description', '')}",
            f"评分: {task.get('score', 0)}（{task.get('grade', '')}级）",
            f"及时性: {task.get('score_timeliness', '-')}",
            f"质量: {task.get('score_quality', '-')}",
        ]
        if feedback_text:
            lines.append(f"反馈摘要: {feedback_text[:500]}")
        return "\n".join(lines)

    def _build_kpi_knowledge(
        self, score_row: dict[str, Any], scores_detail: Any
    ) -> str:
        lines = [
            f"员工: {score_row.get('employee_id', '')}",
            f"周期: {score_row.get('period_key', '')}",
            f"总分: {score_row.get('total_score', 0)}（{score_row.get('grade', '')}级）",
        ]
        if isinstance(scores_detail, dict):
            for name, detail in scores_detail.items():
                if isinstance(detail, dict):
                    lines.append(
                        f"  - {name}: {detail.get('raw_score', '-')}"
                    )
        return "\n".join(lines)
