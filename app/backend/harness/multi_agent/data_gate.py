"""A3 Data Sufficiency Gate - pure rule-based, NO LLM calls.

Checks whether the minimum required fields are present for each task type
before allowing the pipeline to proceed.
"""
import logging
from typing import Any

from harness.multi_agent.schemas import AgentInput, DataSufficiency

logger = logging.getLogger(__name__)

TASK_FIELD_REQUIREMENTS: dict[str, list[str]] = {
    "new_direction": [
        "platform",
        "market",
        "target_persona",
    ],
    "link_analysis": [
        "platform",
        "market",
        "data.impressions",
        "data.clicks|data.ctr",
    ],
    "market_expansion": [
        "platform",
        "market",
        "target_persona",
        "niche",
    ],
    "scaling": [
        "data.orders",
        "data.gmv",
        "data.gross_margin",
        "data.ad_spend",
    ],
    "team_action": [
        "question",
    ],
    "content_event": [
        "platform",
        "market",
    ],
    "review": [
        "question",
    ],
}


def _resolve_field(input_data: AgentInput, field_path: str) -> Any:
    """Resolve a dot-separated field path on AgentInput.

    Supports '|' for OR conditions (e.g. 'data.clicks|data.ctr' means
    either one being present is sufficient).
    """
    parts = field_path.split(".")
    obj: Any = input_data
    for part in parts:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            obj = getattr(obj, part, None)
    return obj


def _field_present(input_data: AgentInput, field_spec: str) -> bool:
    """Check whether a field spec is satisfied.

    A spec can contain '|' to denote alternatives.
    """
    alternatives = field_spec.split("|")
    for alt in alternatives:
        val = _resolve_field(input_data, alt.strip())
        if val is not None and val != "" and val != 0:
            return True
    return False


class DataGate:
    """Pure rule-based data sufficiency gate (A3).

    Returns a tuple of (DataSufficiency, list_of_missing_fields).
    """

    def check(self, input_data: AgentInput) -> tuple[DataSufficiency, list[str]]:
        task_type = input_data.task_type
        requirements = TASK_FIELD_REQUIREMENTS.get(task_type)

        if requirements is None:
            logger.warning(f"No field requirements defined for task_type='{task_type}', allowing research_only")
            return DataSufficiency.RESEARCH_ONLY, [f"unknown_task_type:{task_type}"]

        missing: list[str] = []
        for field_spec in requirements:
            if not _field_present(input_data, field_spec):
                missing.append(field_spec)

        if not missing:
            return DataSufficiency.SUFFICIENT, []

        critical_missing = len(missing)
        total_required = len(requirements)
        ratio = critical_missing / total_required if total_required > 0 else 1.0

        if ratio > 0.5:
            return DataSufficiency.INSUFFICIENT, missing

        return DataSufficiency.RESEARCH_ONLY, missing


data_gate = DataGate()
