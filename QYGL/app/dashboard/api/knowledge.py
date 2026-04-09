"""P10: Knowledge management — list with category tree, upload, dream candidates."""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import Database, new_id
from app.core.enums import KnowledgeScope, KnowledgeSource, KnowledgeStatus
from app.core.uploads import save_upload
from app.dashboard.app import _global_context, render

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _knowledge_file_summary(file_path: Path, ext: str, max_rows: int = 5) -> str:
    """Build a short text summary for tabular / text uploads."""
    ext_l = ext.lower()
    if ext_l == ".csv":
        try:
            rows: list[list[str]] = []
            with file_path.open(encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    rows.append([str(c)[:200] for c in row])
            body = "\n".join("\t".join(r) for r in rows)
            return f"CSV 预览（前 {max_rows} 行）:\n{body}" if body else "CSV 文件为空。"
        except Exception as e:
            return f"CSV 预览失败: {e}"

    if ext_l in (".xlsx", ".xls"):
        try:
            import openpyxl
        except ImportError:
            return "（无法预览 Excel：未安装 openpyxl）"
        try:
            wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
            ws = wb.active
            lines: list[str] = []
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= max_rows:
                    break
                cells = ["" if v is None else str(v)[:200] for v in row]
                lines.append("\t".join(cells))
            wb.close()
            body = "\n".join(lines)
            return f"表格预览（前 {max_rows} 行）:\n{body}" if body else "表格为空。"
        except Exception as e:
            return f"表格预览失败: {e}"

    if ext_l in (".txt", ".md"):
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")[:2000]
            return f"文本预览:\n{text}"
        except Exception as e:
            return f"文本预览失败: {e}"

    return f"已上传文件类型 {ext_l}，无自动文本预览。"


@router.get("", response_class=HTMLResponse)
async def knowledge_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    category = request.query_params.get("category", "")
    scope = request.query_params.get("scope", "")
    status = request.query_params.get("status", "")

    conditions: dict = {}
    if category:
        conditions["category"] = category
    if scope:
        conditions["scope"] = scope
    if status:
        conditions["status"] = status
    else:
        conditions["status"] = KnowledgeStatus.ACTIVE.value

    items = db.query("knowledge", conditions, order_by="created_at DESC", limit=200)

    categories_raw = db.execute("SELECT DISTINCT category FROM knowledge WHERE category != ''")
    categories = [r["category"] for r in categories_raw]

    ctx["items"] = items
    ctx["categories"] = categories
    ctx["category_filter"] = category
    ctx["scope_filter"] = scope
    ctx["status_filter"] = status
    ctx["scopes"] = [s.value for s in KnowledgeScope]
    ctx["stats"] = {
        "total": len(items),
        "company": sum(1 for i in items if i.get("scope") == "company"),
        "department": sum(1 for i in items if i.get("scope") == "department"),
    }
    ctx["upload_error"] = request.query_params.get("upload_error", "")

    return render(request, "pages/knowledge.html", ctx)


@router.post("")
async def create_knowledge(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    category: str = Form(""),
    scope: str = Form("company"),
    department: str = Form(""),
):
    db = Database.get_instance()
    user = getattr(request.state, "user", {})

    db.insert("knowledge", {
        "id": new_id(),
        "title": title,
        "content": content,
        "category": category,
        "scope": scope,
        "department": department,
        "source": KnowledgeSource.MANUAL.value,
        "status": KnowledgeStatus.ACTIVE.value,
        "created_by": user.get("id", ""),
    })
    return RedirectResponse("/knowledge?" + urlencode({"msg": "知识已添加"}), status_code=302)


@router.post("/upload")
async def upload_knowledge_file(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(""),
    scope: str = Form("company"),
    department: str = Form(""),
):
    db = Database.get_instance()
    user = getattr(request.state, "user", {})

    try:
        meta = await save_upload(file)
    except ValueError as e:
        return RedirectResponse(
            f"/knowledge?upload_error={quote(str(e))}",
            status_code=302,
        )

    path = Path(meta["path"])
    summary = _knowledge_file_summary(path, meta.get("ext", ""))
    stored_name = path.name
    content = f"{summary}\n\n文件路径: /uploads/{stored_name}"

    db.insert(
        "knowledge",
        {
            "id": new_id(),
            "title": title,
            "content": content,
            "category": category,
            "scope": scope,
            "department": department,
            "source": KnowledgeSource.MANUAL.value,
            "status": KnowledgeStatus.ACTIVE.value,
            "created_by": user.get("id", ""),
        },
    )
    return RedirectResponse("/knowledge", status_code=302)


@router.get("/pending", response_class=HTMLResponse)
async def pending_knowledge(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    candidates = db.query("knowledge", {"status": "candidate"}, order_by="created_at DESC", limit=100)

    dream_reports = db.query("dream_reports", order_by="created_at DESC", limit=5)
    dream_candidates = []
    for dr in dream_reports:
        import json
        raw = dr.get("knowledge_candidates_json", "[]")
        if isinstance(raw, str):
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                items = []
        else:
            items = raw
        for item in items:
            item["report_date"] = dr.get("date", "")
            dream_candidates.append(item)

    ctx["candidates"] = candidates
    ctx["dream_candidates"] = dream_candidates

    return render(request, "pages/knowledge_pending.html", ctx)


@router.post("/{knowledge_id}/update")
async def update_knowledge(
    knowledge_id: str,
    title: str = Form(...),
    content: str = Form(...),
    scope: str = Form("company"),
    department: str = Form(""),
    category: str = Form(""),
):
    db = Database.get_instance()
    if not db.get_by_id("knowledge", knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge not found")
    db.update(
        "knowledge",
        knowledge_id,
        {
            "title": title,
            "content": content,
            "scope": scope,
            "department": department,
            "category": category,
        },
    )
    return RedirectResponse("/knowledge", status_code=302)


@router.post("/{knowledge_id}/delete")
async def delete_knowledge(knowledge_id: str):
    db = Database.get_instance()
    if not db.get_by_id("knowledge", knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge not found")
    db.delete("knowledge", knowledge_id)
    return RedirectResponse("/knowledge", status_code=302)


@router.post("/{knowledge_id}/approve")
async def approve_knowledge(knowledge_id: str):
    db = Database.get_instance()
    if not db.get_by_id("knowledge", knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge not found")
    db.update("knowledge", knowledge_id, {"status": KnowledgeStatus.ACTIVE.value})
    return RedirectResponse("/knowledge/pending", status_code=302)


@router.post("/{knowledge_id}/reject")
async def reject_knowledge(knowledge_id: str):
    db = Database.get_instance()
    if not db.get_by_id("knowledge", knowledge_id):
        raise HTTPException(status_code=404, detail="Knowledge not found")
    db.update("knowledge", knowledge_id, {"status": KnowledgeStatus.ARCHIVED.value})
    return RedirectResponse("/knowledge/pending", status_code=302)
