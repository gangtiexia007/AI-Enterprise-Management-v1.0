"""F13 File Parser Skill — extract structured data from uploaded files.

Tools:
    file_parser__parse_excel    — read .xlsx / .xls into list-of-dicts
    file_parser__parse_csv      — read .csv into list-of-dicts
    file_parser__parse_markdown — parse Markdown into sections
    file_parser__parse_text     — split plain text into lines/paragraphs
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from app.core.enums import PermissionLevel
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

ALLOWED_ROOTS = [os.path.abspath("data"), os.path.abspath("knowledge")]


def _validate_path(file_path: str) -> bool:
    abs_path = os.path.abspath(file_path)
    return any(abs_path.startswith(root) for root in ALLOWED_ROOTS)


@tool(permission=PermissionLevel.P0, description="Parse Excel file into structured rows")
def file_parser__parse_excel(
    ctx: ToolContext,
    *,
    file_path: str,
    sheet_name: str | None = None,
    header_row: int = 0,
    max_rows: int = 5000,
) -> dict[str, Any]:
    """Read an Excel file and return ``{columns: [...], rows: [{...}, ...]}``."""
    if not _validate_path(file_path):
        return {"error": f"Access denied: path is outside allowed directories"}
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        import openpyxl
    except ImportError:
        return {"error": "openpyxl is not installed. Run: pip install openpyxl"}

    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
    if ws is None:
        return {"error": "No active sheet found"}

    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        wb.close()
        return {"columns": [], "rows": [], "total": 0}

    headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(all_rows[header_row])]
    data_rows = all_rows[header_row + 1: header_row + 1 + max_rows]

    rows = []
    for raw in data_rows:
        row_dict: dict[str, Any] = {}
        for i, val in enumerate(raw):
            col = headers[i] if i < len(headers) else f"col_{i}"
            row_dict[col] = _serialize_cell(val)
        rows.append(row_dict)

    wb.close()
    return {"columns": headers, "rows": rows, "total": len(rows)}


@tool(permission=PermissionLevel.P0, description="Parse Markdown file into sections")
def file_parser__parse_markdown(
    ctx: ToolContext,
    *,
    file_path: str = "",
    content: str = "",
) -> dict[str, Any]:
    """Parse Markdown into a list of sections with heading level + body."""
    if file_path:
        if not _validate_path(file_path):
            return {"error": f"Access denied: path is outside allowed directories"}
        p = Path(file_path)
        if not p.exists():
            return {"error": f"File not found: {file_path}"}
        content = p.read_text(encoding="utf-8")

    if not content:
        return {"sections": [], "total": 0}

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] = {"level": 0, "heading": "", "body_lines": []}

    for line in content.split("\n"):
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            if current["heading"] or current["body_lines"]:
                current["body"] = "\n".join(current.pop("body_lines")).strip()
                sections.append(current)
            current = {
                "level": len(heading_match.group(1)),
                "heading": heading_match.group(2).strip(),
                "body_lines": [],
            }
        else:
            current["body_lines"].append(line)

    if current["heading"] or current["body_lines"]:
        current["body"] = "\n".join(current.pop("body_lines")).strip()
        sections.append(current)

    return {"sections": sections, "total": len(sections)}


@tool(permission=PermissionLevel.P0, description="Parse plain text file into lines or paragraphs")
def file_parser__parse_text(
    ctx: ToolContext,
    *,
    file_path: str = "",
    content: str = "",
    mode: str = "paragraphs",
) -> dict[str, Any]:
    """Split text into lines or paragraphs.

    *mode*: ``"lines"`` or ``"paragraphs"`` (split on blank lines).
    """
    if file_path:
        if not _validate_path(file_path):
            return {"error": f"Access denied: path is outside allowed directories"}
        p = Path(file_path)
        if not p.exists():
            return {"error": f"File not found: {file_path}"}
        content = p.read_text(encoding="utf-8")

    if not content:
        return {"items": [], "total": 0}

    if mode == "lines":
        items = [line for line in content.split("\n") if line.strip()]
    else:
        raw_paragraphs = re.split(r"\n\s*\n", content)
        items = [p.strip() for p in raw_paragraphs if p.strip()]

    return {"items": items, "total": len(items)}


@tool(permission=PermissionLevel.P0, description="Parse CSV file into structured rows")
def file_parser__parse_csv(
    ctx: ToolContext,
    *,
    file_path: str,
    delimiter: str = ",",
    encoding: str = "utf-8",
    max_rows: int = 5000,
) -> dict[str, Any]:
    """Read a CSV file and return columns + rows."""
    if not _validate_path(file_path):
        return {"error": "Access denied: path is outside allowed directories"}
    p = Path(file_path)
    if not p.exists():
        return {"error": f"File not found: {file_path}"}

    import csv
    rows = []
    columns = []
    with open(str(p), "r", encoding=encoding, errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        columns = reader.fieldnames or []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(dict(row))

    return {"columns": list(columns), "rows": rows, "total": len(rows)}


def _serialize_cell(val: Any) -> Any:
    """Convert Excel cell values to JSON-safe types."""
    if val is None:
        return None
    from datetime import date, datetime
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, (int, float, str, bool)):
        return val
    return str(val)
