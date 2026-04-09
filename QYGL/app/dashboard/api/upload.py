"""File upload + intelligent parsing endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, JSONResponse

from app.core.database import Database, new_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["upload"])

UPLOAD_DIR = Path("data/uploads")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".json", ".txt", ".md"}


@router.post("/api/upload/parse")
async def upload_and_parse(
    request: Request,
    file: UploadFile = File(...),
    team_id: str = Form(""),
    description: str = Form(""),
):
    """Upload a file and parse it into structured data."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            {"error": f"不支持的文件类型: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}"},
            status_code=400,
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = new_id()
    safe_name = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_name

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse({"error": "文件过大，最大 50MB"}, status_code=400)

    file_path.write_bytes(content)

    parsed = _parse_file(str(file_path), ext)

    db = Database.get_instance()
    db.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL DEFAULT '',
            filename TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL DEFAULT '',
            file_type TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            parse_result_json TEXT NOT NULL DEFAULT '{}',
            row_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'parsed',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    row_count = len(parsed.get("rows", []))

    db.insert("uploaded_files", {
        "id": file_id,
        "team_id": team_id,
        "filename": file.filename or safe_name,
        "file_path": str(file_path),
        "file_type": ext,
        "file_size": len(content),
        "description": description,
        "parse_result_json": json.dumps({
            "columns": parsed.get("columns", []),
            "row_count": row_count,
            "preview": parsed.get("rows", [])[:5],
        }, ensure_ascii=False, default=str),
        "row_count": row_count,
        "status": "parsed",
        "created_at": now,
    })

    logger.info("File uploaded and parsed: %s (%s, %d rows)", file.filename, ext, row_count)

    result = {
        "status": "parsed" if "error" not in parsed else "error",
        "file_id": file_id,
        "filename": file.filename,
        "columns": parsed.get("columns", []),
        "row_count": row_count,
        "preview": parsed.get("rows", [])[:10],
    }
    if "error" in parsed:
        result["error"] = parsed["error"]
    return JSONResponse(result)


@router.get("/api/uploads")
async def list_uploads(request: Request):
    """List uploaded files."""
    db = Database.get_instance()
    try:
        rows = db.execute(
            "SELECT id, team_id, filename, file_type, file_size, row_count, status, created_at "
            "FROM uploaded_files ORDER BY created_at DESC LIMIT 100"
        )
    except Exception:
        rows = []
    return JSONResponse({"items": rows})


def _parse_file(file_path: str, ext: str) -> dict[str, Any]:
    """Parse a file and return {columns, rows}."""
    if ext in (".xlsx", ".xls"):
        return _parse_excel(file_path)
    elif ext == ".csv":
        return _parse_csv(file_path)
    elif ext == ".json":
        return _parse_json(file_path)
    elif ext in (".txt", ".md"):
        return _parse_text(file_path)
    return {"columns": [], "rows": []}


def _parse_excel(file_path: str) -> dict[str, Any]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        if not ws:
            return {"columns": [], "rows": []}

        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            wb.close()
            return {"columns": [], "rows": []}

        headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(all_rows[0])]
        rows = []
        for raw in all_rows[1:5001]:
            row_dict = {}
            for i, val in enumerate(raw):
                col = headers[i] if i < len(headers) else f"col_{i}"
                row_dict[col] = _serialize(val)
            rows.append(row_dict)
        wb.close()
        return {"columns": headers, "rows": rows}
    except Exception as e:
        return {"columns": [], "rows": [], "error": str(e)}


def _parse_csv(file_path: str) -> dict[str, Any]:
    import csv
    rows = []
    columns = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            columns = list(reader.fieldnames or [])
            for i, row in enumerate(reader):
                if i >= 5000:
                    break
                rows.append(dict(row))
    except Exception as e:
        return {"columns": [], "rows": [], "error": str(e)}
    return {"columns": columns, "rows": rows}


def _parse_json(file_path: str) -> dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            columns = list(data[0].keys()) if isinstance(data[0], dict) else []
            return {"columns": columns, "rows": data[:5000]}
        elif isinstance(data, dict):
            return {"columns": list(data.keys()), "rows": [data]}
    except Exception as e:
        return {"columns": [], "rows": [], "error": str(e)}
    return {"columns": [], "rows": []}


def _parse_text(file_path: str) -> dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        rows = [{"line_number": i + 1, "content": line.rstrip()} for i, line in enumerate(lines) if line.strip()]
        return {"columns": ["line_number", "content"], "rows": rows[:5000]}
    except Exception as e:
        return {"columns": [], "rows": [], "error": str(e)}


def _serialize(val):
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
