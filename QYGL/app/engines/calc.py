"""F21: Calc Engine + Reward Linkage — formula evaluation and reward computation.

Uses simpleeval for safe formula evaluation.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

from simpleeval import simple_eval, InvalidExpression

from app.core.database import new_id
from app.core.enums import RewardStatus
from app.core.exceptions import ValidationError
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "int": int,
    "float": float,
    "ceil": math.ceil,
    "floor": math.floor,
}


class CalcEngine(EngineBase):
    """Evaluates formulas and computes reward amounts linked to KPI grades."""

    def evaluate_formula(
        self, formula: str, variables: dict[str, Any] | None = None
    ) -> float:
        """Safely evaluate a math formula string with given variables."""
        if not formula:
            raise ValidationError("Formula must not be empty")

        names = dict(variables or {})
        try:
            result = simple_eval(formula, names=names, functions=SAFE_FUNCTIONS)
            return float(result)
        except InvalidExpression as exc:
            raise ValidationError(f"Invalid formula: {exc}") from exc
        except Exception as exc:
            raise ValidationError(f"Formula evaluation error: {exc}") from exc

    def calculate_reward(
        self,
        employee_id: str,
        period: str,
        kpi_score_id: str,
    ) -> dict[str, Any]:
        """Match a RewardRule by KPI grade, evaluate its formula, and create a RewardCalculation."""
        kpi_score = self._get_by_id("kpi_scores", kpi_score_id)
        grade = kpi_score.get("grade", "")
        total_score = float(kpi_score.get("total_score", 0))
        team_id = self._resolve_team_id(employee_id)

        rules = self._query("reward_rules", {"team_id": team_id, "kpi_grade": grade})
        if not rules:
            rules = self._query("reward_rules", {"team_id": team_id, "kpi_grade": "*"})

        if not rules:
            logger.warning("No reward rule found for team=%s grade=%s", team_id, grade)
            return self._create_reward_record(
                employee_id, team_id, period, kpi_score_id,
                rule_id="", amount=0.0, formula="", variables={},
            )

        rule = rules[0]
        formula = rule.get("formula", "0")
        variables = {
            "score": total_score,
            "grade_num": self._grade_to_num(grade),
            "base": 1000.0,
        }

        amount = self.evaluate_formula(formula, variables)
        amount = round(amount, 2)

        return self._create_reward_record(
            employee_id, team_id, period, kpi_score_id,
            rule_id=rule["id"], amount=amount,
            formula=formula, variables=variables,
        )

    def _create_reward_record(
        self,
        employee_id: str,
        team_id: str,
        period: str,
        kpi_score_id: str,
        rule_id: str,
        amount: float,
        formula: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "id": new_id(),
            "employee_id": employee_id,
            "team_id": team_id,
            "period": period,
            "kpi_score_id": kpi_score_id,
            "rule_id": rule_id,
            "calculated_amount": amount,
            "formula_used": formula,
            "variables_json": variables,
            "status": RewardStatus.CALCULATED.value,
            "created_at": self._now_iso(),
        }
        self._insert("reward_calculations", record)
        logger.info(
            "Reward calculated: employee=%s amount=%.2f rule=%s",
            employee_id, amount, rule_id,
        )
        return record

    def list_reward_rules(self, team_id: str) -> list[dict[str, Any]]:
        return self._query("reward_rules", {"team_id": team_id})

    def create_reward_rule(
        self,
        team_id: str,
        name: str,
        kpi_grade: str,
        formula: str,
        description: str = "",
    ) -> dict[str, Any]:
        if not team_id or not name or not formula:
            raise ValidationError("team_id, name, and formula are required")

        self.evaluate_formula(formula, {"score": 80, "grade_num": 3, "base": 1000})

        rule = {
            "id": new_id(),
            "team_id": team_id,
            "name": name,
            "kpi_grade": kpi_grade,
            "formula": formula,
            "description": description,
            "created_at": self._now_iso(),
        }
        self._insert("reward_rules", rule)
        logger.info("Reward rule created: %s '%s'", rule["id"], name)
        return rule

    def get_reward_history(
        self, employee_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        return self._query(
            "reward_calculations",
            {"employee_id": employee_id},
            order_by="created_at DESC",
            limit=limit,
        )

    def _resolve_team_id(self, employee_id: str) -> str:
        emp = self._get_by_id_optional("employees", employee_id)
        return emp.get("team_id", "") if emp else ""

    @staticmethod
    def _grade_to_num(grade: str) -> int:
        return {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}.get(grade.upper(), 0)
