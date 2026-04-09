"""P04: Quick commands management."""

from __future__ import annotations

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import RedirectResponse

from app.core.database import Database, new_id
from app.dashboard.app import templates, _global_context, render

router = APIRouter(prefix="/commands", tags=["commands"])

BUILTIN_COMMANDS = [
    {"name": "/日报", "description": "生成今日工作日报", "category": "报告", "builtin": True},
    {"name": "/KPI", "description": "查看当前KPI进度", "category": "绩效", "builtin": True},
    {"name": "/任务", "description": "查看待办任务列表", "category": "任务", "builtin": True},
    {"name": "/申诉", "description": "发起考核申诉流程", "category": "申诉", "builtin": True},
]


def _ensure_builtins(db: Database) -> None:
    for cmd in BUILTIN_COMMANDS:
        existing = db.execute(
            "SELECT id FROM commands WHERE name=? AND builtin=1", (cmd["name"],)
        )
        if not existing:
            db.insert("commands", {
                "id": new_id(),
                "name": cmd["name"],
                "description": cmd["description"],
                "category": cmd["category"],
                "builtin": True,
                "enabled": True,
                "response_template": "",
            })


@router.get("", response_class=HTMLResponse)
async def commands_page(request: Request):
    db = Database.get_instance()
    _ensure_builtins(db)
    ctx = _global_context(request)

    commands = db.query("commands", order_by="builtin DESC, name ASC", limit=100)
    ctx["commands"] = commands
    ctx["builtin_count"] = sum(1 for c in commands if c.get("builtin"))
    ctx["custom_count"] = sum(1 for c in commands if not c.get("builtin"))
    return render(request, "pages/commands.html", ctx)


@router.post("", response_class=HTMLResponse)
async def create_command(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("自定义"),
    response_template: str = Form(""),
):
    db = Database.get_instance()
    if not name.startswith("/"):
        name = "/" + name

    db.insert("commands", {
        "id": new_id(),
        "name": name,
        "description": description,
        "category": category,
        "builtin": False,
        "enabled": True,
        "response_template": response_template,
    })
    return RedirectResponse("/commands", status_code=302)


@router.put("/{cmd_id}")
async def update_command(request: Request, cmd_id: str):
    db = Database.get_instance()
    body = await request.json()
    db.update("commands", cmd_id, body)
    return JSONResponse({"ok": True})


@router.post("/{cmd_id}/toggle")
async def toggle_command(cmd_id: str):
    db = Database.get_instance()
    cmd = db.get_by_id("commands", cmd_id)
    if cmd:
        db.update("commands", cmd_id, {"enabled": not cmd.get("enabled", True)})
    return RedirectResponse("/commands", status_code=302)


@router.post("/{cmd_id}/delete")
async def delete_command(cmd_id: str):
    db = Database.get_instance()
    cmd = db.get_by_id("commands", cmd_id)
    if cmd and cmd.get("builtin"):
        return RedirectResponse("/commands", status_code=302)
    if cmd:
        db.delete("commands", cmd_id)
    return RedirectResponse("/commands", status_code=302)
