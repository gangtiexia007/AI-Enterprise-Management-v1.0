"""F14: SKILL.md Parser — convert SKILL.md files into prompt-based skill templates.

SKILL.md format (simplified)::

    # Skill Name
    Display name for the skill.

    ## Description
    What this skill does.

    ## Tools
    ### tool_name
    - description: What the tool does
    - permission: P0
    - parameters:
      - param1: description
      - param2: description

    ## Prompt Template
    System prompt fragment to inject when this skill is active.

The parser extracts structure and registers it into the ``SkillRegistry``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.core.enums import PermissionLevel, SkillSource

logger = logging.getLogger(__name__)


def parse_skill_md(content: str) -> dict[str, Any]:
    """Parse a SKILL.md string into a structured dict.

    Returns::

        {
            "name": "...",
            "display_name": "...",
            "description": "...",
            "tools": [{"name": ..., "description": ..., "permission": ..., "parameters": {...}}],
            "prompt_template": "...",
            "config": {...},
        }
    """
    lines = content.split("\n")
    result: dict[str, Any] = {
        "name": "",
        "display_name": "",
        "description": "",
        "tools": [],
        "prompt_template": "",
        "config": {},
    }

    current_section = ""
    current_tool: dict[str, Any] | None = None
    section_lines: list[str] = []

    def _flush_section() -> None:
        nonlocal current_tool
        text = "\n".join(section_lines).strip()
        if current_section == "description":
            result["description"] = text
        elif current_section == "prompt_template":
            result["prompt_template"] = text
        elif current_section == "tool" and current_tool:
            current_tool["description"] = current_tool.get("description", "") or text
            result["tools"].append(current_tool)
            current_tool = None

    for line in lines:
        stripped = line.strip()

        h1 = re.match(r"^#\s+(.+)$", stripped)
        if h1:
            _flush_section()
            name_raw = h1.group(1).strip()
            result["display_name"] = name_raw
            result["name"] = re.sub(r"[^a-zA-Z0-9_]", "_", name_raw.lower()).strip("_")
            current_section = ""
            section_lines = []
            continue

        h2 = re.match(r"^##\s+(.+)$", stripped)
        if h2:
            _flush_section()
            sec = h2.group(1).strip().lower().replace(" ", "_")
            current_section = sec
            section_lines = []
            continue

        h3 = re.match(r"^###\s+(.+)$", stripped)
        if h3:
            if current_tool:
                _flush_section()
            tool_name = h3.group(1).strip()
            current_tool = {
                "name": tool_name,
                "description": "",
                "permission": PermissionLevel.P0.value,
                "parameters": {},
            }
            current_section = "tool"
            section_lines = []
            continue

        if current_section == "tool" and current_tool:
            perm_match = re.match(r"^-\s*permission:\s*(P\d)$", stripped, re.IGNORECASE)
            if perm_match:
                level_str = perm_match.group(1).upper()
                level_map = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
                current_tool["permission"] = level_map.get(level_str, 0)
                continue

            desc_match = re.match(r"^-\s*description:\s*(.+)$", stripped)
            if desc_match:
                current_tool["description"] = desc_match.group(1).strip()
                continue

            param_match = re.match(r"^\s+-\s*(\w+):\s*(.+)$", stripped)
            if param_match:
                current_tool["parameters"][param_match.group(1)] = param_match.group(2).strip()
                continue

        section_lines.append(line)

    _flush_section()
    return result


def load_skill_md_file(path: str | Path) -> dict[str, Any]:
    """Read and parse a SKILL.md file."""
    p = Path(path)
    if not p.exists():
        logger.warning("SKILL.md not found: %s", p)
        return {}
    content = p.read_text(encoding="utf-8")
    return parse_skill_md(content)


def register_skill_md(
    path: str | Path,
    is_global: bool = False,
) -> None:
    """Parse a SKILL.md file and register it into the SkillRegistry."""
    parsed = load_skill_md_file(path)
    if not parsed or not parsed.get("name"):
        logger.warning("Could not parse skill from %s", path)
        return

    from app.skills.registry import SkillRegistry

    registry = SkillRegistry.get_instance()
    registry.register_custom_skill(
        name=parsed["name"],
        display_name=parsed.get("display_name", parsed["name"]),
        description=parsed.get("description", ""),
        tools_json=parsed.get("tools", []),
        config_json={
            "prompt_template": parsed.get("prompt_template", ""),
            **parsed.get("config", {}),
        },
        is_global=is_global,
    )
    logger.info("Registered SKILL.md: %s from %s", parsed["name"], path)


def scan_and_register_skill_mds(directory: str | Path, is_global: bool = False) -> int:
    """Walk a directory tree for ``SKILL.md`` files and register each one."""
    d = Path(directory)
    if not d.is_dir():
        logger.warning("Skill directory not found: %s", d)
        return 0
    count = 0
    for md_file in d.rglob("SKILL.md"):
        register_skill_md(md_file, is_global=is_global)
        count += 1
    logger.info("Scanned %s — found %d SKILL.md files", d, count)
    return count
