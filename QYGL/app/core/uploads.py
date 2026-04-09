"""File upload handling — save to local storage, validate type/size."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

UPLOAD_DIR = Path("data/uploads")
ALLOWED_EXTENSIONS = {
    ".xlsx",
    ".xls",
    ".csv",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".txt",
    ".md",
    ".doc",
    ".docx",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


async def save_upload(file: UploadFile) -> dict:
    """Save uploaded file and return metadata dict."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "file").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("文件超过20MB限制")

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}{ext}"
    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
        "ext": ext,
    }
