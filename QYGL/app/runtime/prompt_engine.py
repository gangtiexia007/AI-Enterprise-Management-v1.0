"""F11: Prompt Engine — system prompt variable interpolation and template rendering.

Renders the team's ``system_prompt`` by replacing ``{variable}`` placeholders with
live context values.  If a variable is missing, the entire containing paragraph
(text block separated by blank lines) is silently removed.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def _resolve(key: str, variables: dict[str, Any]) -> str | None:
    """Resolve a dotted key like ``employee.name`` against a flat or nested dict.

    Returns ``None`` when the key is absent or its value is empty.
    """
    if key in variables:
        val = variables[key]
        return str(val) if val not in (None, "") else None

    parts = key.split(".")
    obj: Any = variables
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return None
        if obj is None:
            return None
    return str(obj) if obj not in (None, "") else None


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (separated by one or more blank lines)."""
    return re.split(r"\n\s*\n", text)


def _render_paragraph(paragraph: str, variables: dict[str, Any]) -> str | None:
    """Render one paragraph.  Returns ``None`` if any variable is missing."""
    placeholders = _VAR_PATTERN.findall(paragraph)
    if not placeholders:
        return paragraph

    for key in placeholders:
        resolved = _resolve(key, variables)
        if resolved is None:
            logger.debug("Missing variable '%s' — skipping paragraph", key)
            return None

    def _replacer(m: re.Match) -> str:
        return _resolve(m.group(1), variables) or ""

    return _VAR_PATTERN.sub(_replacer, paragraph)


class PromptEngine:
    """Renders system prompts with variable interpolation.

    Variables are supplied as a flat dict.  Dotted keys (``employee.name``)
    are resolved by walking nested dicts or object attributes.

    Paragraphs containing unresolvable variables are dropped entirely so the
    LLM never sees raw ``{placeholder}`` tokens.
    """

    def render(self, template: str, variables: dict[str, Any]) -> str:
        """Interpolate *template* with *variables*, dropping incomplete paragraphs."""
        if not template:
            return ""

        paragraphs = _split_paragraphs(template)
        rendered: list[str] = []

        for para in paragraphs:
            result = _render_paragraph(para, variables)
            if result is not None:
                rendered.append(result)

        return "\n\n".join(rendered)

    def build_variables(
        self,
        *,
        team: dict[str, Any] | None = None,
        employee: dict[str, Any] | None = None,
        kpi_progress: str = "",
        team_status_summary: str = "",
        current_plan_summary: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the standard variable dict consumed by ``render``.

        Flattens ``team.*`` and ``employee.*`` so that both ``{team_name}``
        and ``{team.name}`` resolve correctly.
        """
        v: dict[str, Any] = {}

        if team:
            v["team"] = team
            v["team_name"] = team.get("name", "")
            v["team_display_name"] = team.get("display_name", "")
            v["team_department"] = team.get("department", "")
            v["team_automation_profile"] = team.get("automation_profile", "")

        if employee:
            v["employee"] = employee
            v["employee_name"] = employee.get("name", "")
            v["employee_role"] = employee.get("role", "")
            v["employee_department"] = employee.get("department", "")

        if kpi_progress:
            v["kpi_progress"] = kpi_progress
            v["team_kpi_progress"] = kpi_progress
            if team:
                v.setdefault("team", {})["kpi_progress"] = kpi_progress

        if team_status_summary:
            v["team_status_summary"] = team_status_summary

        if current_plan_summary:
            v["current_plan_summary"] = current_plan_summary

        if extra:
            v.update(extra)

        return v
