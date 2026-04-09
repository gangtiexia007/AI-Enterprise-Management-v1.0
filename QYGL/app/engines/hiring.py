"""F40: Hiring Module — profile generation, JD creation, interview templates, scoring, onboarding."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.database import new_id
from app.core.exceptions import ResourceNotFound, ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)


class HiringEngine(EngineBase):
    """End-to-end hiring support: profile → JD → interview → onboarding."""

    # ── Hiring Profile ────────────────────────────────────────────

    def create_hiring_profile(
        self,
        team_id: str,
        source: str = "auto",
    ) -> dict[str, Any]:
        """Generate a hiring profile from top 30% KPI performers or from scratch.

        Args:
            source: "auto" (derive from top performers) or "manual" (empty template)
        """
        if source == "auto":
            profile_data = self._derive_from_top_performers(team_id)
        else:
            profile_data = self._empty_profile_template()

        profile = {
            "id": new_id(),
            "team_id": team_id,
            "profile_json": profile_data,
            "source": source,
            "created_at": self._now_iso(),
        }
        self._insert("hiring_profiles", profile)
        logger.info("Hiring profile created: %s source=%s", profile["id"], source)
        return profile

    def _derive_from_top_performers(self, team_id: str) -> dict[str, Any]:
        scores = self._execute(
            "SELECT ks.* FROM kpi_scores ks "
            "JOIN employees e ON e.id = ks.employee_id "
            "WHERE e.team_id = ? "
            "ORDER BY ks.total_score DESC",
            (team_id,),
        )
        if not scores:
            return self._empty_profile_template()

        top_30_count = max(1, len(scores) * 30 // 100)
        top_scores = scores[:top_30_count]

        avg_score = sum(float(s.get("total_score", 0)) for s in top_scores) / len(top_scores)
        common_traits: list[str] = []

        for s in top_scores:
            detail = self._parse_json_field(s.get("scores_json", "{}"))
            if isinstance(detail, dict):
                for name, d in detail.items():
                    if isinstance(d, dict) and float(d.get("raw_score", 0)) >= 85:
                        common_traits.append(name)

        trait_counts: dict[str, int] = {}
        for t in common_traits:
            trait_counts[t] = trait_counts.get(t, 0) + 1
        top_traits = sorted(trait_counts, key=trait_counts.get, reverse=True)[:5]  # type: ignore[arg-type]

        return {
            "derived_from": "top_30_percent",
            "sample_size": len(top_scores),
            "avg_kpi_score": round(avg_score, 2),
            "key_competencies": top_traits,
            "preferred_grade": "A" if avg_score >= 90 else "B",
            "notes": "Auto-generated from KPI data",
        }

    @staticmethod
    def _empty_profile_template() -> dict[str, Any]:
        return {
            "derived_from": "manual",
            "key_competencies": [],
            "preferred_grade": "",
            "notes": "",
        }

    # ── JD Generation ─────────────────────────────────────────────

    def generate_jd(
        self, team_id: str, position: str
    ) -> str:
        """Generate a job description from profile + knowledge base.
        
        V1 placeholder: structured template. Future: LLM-generated.
        """
        profiles = self._query("hiring_profiles", {"team_id": team_id}, limit=1)
        profile_data = {}
        if profiles:
            raw = profiles[0].get("profile_json", "{}")
            profile_data = self._parse_json_field(raw) if isinstance(raw, str) else raw

        competencies = profile_data.get("key_competencies", [])
        comp_text = "、".join(competencies) if competencies else "待补充"

        jd = (
            f"【职位名称】{position}\n"
            f"【所属团队】{team_id}\n\n"
            f"【职位描述】\n"
            f"我们正在寻找优秀的 {position}，加入我们的团队。\n\n"
            f"【核心能力要求】\n{comp_text}\n\n"
            f"【参考标准】\n"
            f"基于团队高绩效成员画像，目标综合绩效等级："
            f"{profile_data.get('preferred_grade', 'B')} 级以上。\n\n"
            f"【基于知识库补充】\n（待 LLM 补充）"
        )

        logger.info("JD generated for team=%s position=%s", team_id, position)
        return jd

    # ── Interview Template ────────────────────────────────────────

    def create_interview_template(
        self,
        team_id: str,
        position: str,
        questions: list[str] | None = None,
    ) -> dict[str, Any]:
        template = {
            "id": new_id(),
            "team_id": team_id,
            "position": position,
            "required_questions": questions or self._default_questions(),
            "optional_questions": [],
            "scoring_criteria_json": {
                "professional_skill": {"weight": 0.4, "description": "专业能力"},
                "communication": {"weight": 0.2, "description": "沟通能力"},
                "problem_solving": {"weight": 0.2, "description": "解决问题能力"},
                "culture_fit": {"weight": 0.2, "description": "文化匹配度"},
            },
            "created_at": self._now_iso(),
        }
        self._insert("interview_templates", template)
        logger.info("Interview template created: %s for %s", template["id"], position)
        return template

    @staticmethod
    def _default_questions() -> list[str]:
        return [
            "请简述您过往最成功的一个项目经历。",
            "遇到团队成员意见不一致时，您通常如何处理？",
            "请描述一个您主动发现并解决问题的案例。",
            "您对这个岗位的理解是什么？",
            "您的职业规划是什么？",
        ]

    # ── Candidate Scoring ─────────────────────────────────────────

    def score_candidate(
        self,
        candidate_id: str,
        answers: dict[str, float],
    ) -> dict[str, Any]:
        """Evaluate a candidate against interview criteria.

        Args:
            answers: dict mapping criterion_key → score (0-100)
        """
        candidate = self._get_by_id("candidates", candidate_id)
        team_id = candidate.get("team_id", "")

        templates = self._query(
            "interview_templates",
            {"team_id": team_id, "position": candidate.get("position", "")},
            limit=1,
        )

        if templates:
            criteria = self._parse_json_field(
                templates[0].get("scoring_criteria_json", "{}")
            )
        else:
            criteria = {
                "professional_skill": {"weight": 0.4},
                "communication": {"weight": 0.2},
                "problem_solving": {"weight": 0.2},
                "culture_fit": {"weight": 0.2},
            }

        total = 0.0
        total_weight = 0.0
        detail: dict[str, Any] = {}

        for key, meta in criteria.items():
            weight = float(meta.get("weight", 0.25)) if isinstance(meta, dict) else 0.25
            score = float(answers.get(key, 0))
            weighted = score * weight
            total += weighted
            total_weight += weight
            detail[key] = {"raw": score, "weight": weight, "weighted": round(weighted, 2)}

        overall = round(total / total_weight, 2) if total_weight > 0 else 0.0

        self._update("candidates", candidate_id, {
            "interview_scores_json": detail,
            "overall_score": overall,
            "status": "scored",
        })

        logger.info("Candidate scored: %s → %.2f", candidate_id, overall)
        return {
            "candidate_id": candidate_id,
            "scores": detail,
            "overall_score": overall,
        }

    # ── Onboarding Plan ───────────────────────────────────────────

    def create_onboarding_plan(
        self,
        team_id: str,
        employee_id: str,
    ) -> dict[str, Any]:
        """Create a per-team configurable onboarding plan."""
        plan_steps = self._get_team_onboarding_steps(team_id)

        plan = {
            "id": new_id(),
            "team_id": team_id,
            "employee_id": employee_id,
            "plan_json": {
                "steps": plan_steps,
                "total_steps": len(plan_steps),
                "completed_steps": 0,
            },
            "progress": 0.0,
            "status": "active",
            "created_at": self._now_iso(),
        }
        self._insert("onboarding_plans", plan)
        logger.info("Onboarding plan created: %s for employee %s", plan["id"], employee_id)
        return plan

    def _get_team_onboarding_steps(self, team_id: str) -> list[dict[str, Any]]:
        """Load team-specific onboarding steps or return defaults."""
        team = self._get_by_id_optional("teams", team_id)
        if team:
            data_scope = self._parse_json_field(team.get("data_scope_json", "{}"))
            if isinstance(data_scope, dict) and "onboarding_steps" in data_scope:
                return data_scope["onboarding_steps"]

        return [
            {"day": 1, "task": "系统账号开通与权限配置", "category": "IT"},
            {"day": 1, "task": "团队介绍与组织架构说明", "category": "HR"},
            {"day": 2, "task": "业务流程与 SOP 培训", "category": "business"},
            {"day": 3, "task": "工具与系统操作培训", "category": "IT"},
            {"day": 5, "task": "首个任务分配与导师对接", "category": "business"},
            {"day": 7, "task": "第一周回顾与反馈", "category": "HR"},
            {"day": 14, "task": "两周适应评估", "category": "HR"},
            {"day": 30, "task": "月度考核与转正评估", "category": "HR"},
        ]
