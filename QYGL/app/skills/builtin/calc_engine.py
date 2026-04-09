"""F13 Calc Engine Skill — sandboxed formula evaluation via simpleeval.

Tools:
    calc_engine__evaluate       — evaluate a single formula
    calc_engine__batch_evaluate — evaluate multiple formulas in one call
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.core.enums import PermissionLevel
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

SAFE_FUNCTIONS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "log": math.log,
    "log10": math.log10,
    "pow": pow,
}

SAFE_NAMES = {
    "pi": math.pi,
    "e": math.e,
    "true": True,
    "false": False,
    "True": True,
    "False": False,
}


def _evaluate_formula(
    formula: str,
    variables: dict[str, Any] | None = None,
) -> Any:
    """Evaluate *formula* using simpleeval with whitelisted functions."""
    names = {**SAFE_NAMES, **(variables or {})}

    try:
        from simpleeval import simple_eval, EvalWithCompoundTypes
        evaluator = EvalWithCompoundTypes(
            names=names,
            functions=SAFE_FUNCTIONS,
        )
        return evaluator.eval(formula)
    except ImportError:
        raise RuntimeError("simpleeval is required but not installed. Run: pip install simpleeval")


@tool(permission=PermissionLevel.P0, description="Evaluate a single formula in a sandboxed environment")
def calc_engine__evaluate(
    ctx: ToolContext,
    *,
    formula: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate *formula* with optional *variables*.

    Example::

        calc_engine__evaluate(formula="base * rate / 100", variables={"base": 5000, "rate": 15})
        → {"result": 750.0, "formula": "base * rate / 100"}
    """
    try:
        result = _evaluate_formula(formula, variables)
        return {"result": result, "formula": formula}
    except Exception as exc:
        return {"error": str(exc), "formula": formula}


@tool(permission=PermissionLevel.P0, description="Evaluate multiple formulas in batch")
def calc_engine__batch_evaluate(
    ctx: ToolContext,
    *,
    formulas: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate a list of formulas.

    Each item in *formulas* should be ``{"formula": "...", "variables": {...}}``.
    Returns a list of results in the same order.
    """
    results: list[dict[str, Any]] = []
    accumulated: dict[str, Any] = {}

    for item in formulas:
        formula = item.get("formula", "")
        variables = {**accumulated, **(item.get("variables") or {})}
        try:
            result = _evaluate_formula(formula, variables)
            entry = {"formula": formula, "result": result}
            label = item.get("label")
            if label:
                accumulated[label] = result
                entry["label"] = label
            results.append(entry)
        except Exception as exc:
            results.append({"formula": formula, "error": str(exc)})

    return results
