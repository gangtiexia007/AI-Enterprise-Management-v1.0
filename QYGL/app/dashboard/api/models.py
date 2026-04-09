"""P12: Model registry — CRUD, API key test, usage stats, budget alerts."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import RedirectResponse

from app.core.database import Database, new_id
from app.core.security import encrypt
from app.dashboard.app import templates, _global_context, render

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_class=HTMLResponse)
async def model_list_page(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    models = db.query("models", order_by="is_default DESC, name ASC", limit=100)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    for m in models:
        usage = db.execute(
            "SELECT SUM(total_tokens) as total FROM model_usage WHERE model_id=? AND date=?",
            (m["id"], today),
        )
        m["today_tokens"] = (usage[0]["total"] or 0) if usage else 0
        daily_limit = m.get("daily_token_limit", 0) or 0
        m["usage_pct"] = round(m["today_tokens"] / daily_limit * 100, 1) if daily_limit > 0 else 0
        m["budget_alert"] = m["usage_pct"] >= 80

    ctx["models"] = models
    ctx["stats"] = {
        "total": len(models),
        "enabled": sum(1 for m in models if m.get("enabled")),
        "alerts": sum(1 for m in models if m.get("budget_alert")),
    }

    return render(request, "pages/models.html", ctx)


@router.post("")
async def create_model(
    request: Request,
    name: str = Form(...),
    provider: str = Form(...),
    api_key: str = Form(""),
    cost_tier: int = Form(1),
    daily_token_limit: int = Form(0),
    monthly_token_limit: int = Form(0),
    is_default: bool = Form(False),
):
    db = Database.get_instance()
    db.insert("models", {
        "id": new_id(),
        "name": name,
        "provider": provider,
        "api_key_encrypted": encrypt(api_key) if api_key else "",
        "cost_tier": cost_tier,
        "daily_token_limit": daily_token_limit,
        "monthly_token_limit": monthly_token_limit,
        "is_default": is_default,
        "enabled": True,
    })
    return RedirectResponse("/models?" + urlencode({"msg": "模型已添加"}), status_code=302)


@router.post("/{model_id}/update")
async def update_model(
    model_id: str,
    name: str = Form(...),
    provider: str = Form(...),
    cost_tier: int = Form(1),
    daily_token_limit: int = Form(0),
    monthly_token_limit: int = Form(0),
    is_default: int = Form(0),
    enabled: int = Form(1),
    api_key: str = Form(""),
):
    db = Database.get_instance()
    model = db.get_by_id("models", model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    data = {
        "name": name,
        "provider": provider,
        "cost_tier": cost_tier,
        "daily_token_limit": daily_token_limit,
        "monthly_token_limit": monthly_token_limit,
        "is_default": 1 if is_default else 0,
        "enabled": 1 if enabled else 0,
    }
    if api_key and api_key.strip():
        data["api_key_encrypted"] = encrypt(api_key.strip())
    db.update("models", model_id, data)
    return RedirectResponse("/models", status_code=302)


@router.post("/{model_id}/delete")
async def delete_model(model_id: str):
    db = Database.get_instance()
    model = db.get_by_id("models", model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    db.delete("models", model_id)
    return RedirectResponse("/models", status_code=302)


@router.post("/{model_id}/toggle")
async def toggle_model_enabled(model_id: str):
    db = Database.get_instance()
    model = db.get_by_id("models", model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    was = 1 if model.get("enabled") else 0
    db.update("models", model_id, {"enabled": 0 if was else 1})
    return RedirectResponse("/models", status_code=302)


@router.post("/{model_id}/test")
async def test_api_key(model_id: str):
    db = Database.get_instance()
    model = db.get_by_id("models", model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    has_key = bool(model.get("api_key_encrypted"))
    return JSONResponse({
        "ok": has_key,
        "model_id": model_id,
        "message": "API Key 已配置" if has_key else "API Key 未配置",
    })


@router.get("/usage", response_class=HTMLResponse)
async def usage_stats(request: Request):
    db = Database.get_instance()
    ctx = _global_context(request)

    usage_rows = db.execute(
        "SELECT model_id, date, SUM(prompt_tokens) as prompt, "
        "SUM(completion_tokens) as completion, SUM(total_tokens) as total "
        "FROM model_usage GROUP BY model_id, date ORDER BY date DESC LIMIT 200"
    )

    models = db.query("models", limit=100)
    model_map = {m["id"]: m.get("name", m["id"]) for m in models}

    for row in usage_rows:
        row["model_name"] = model_map.get(row.get("model_id", ""), "未知")

    budget_alerts = []
    for m in models:
        daily_limit = m.get("daily_token_limit", 0) or 0
        monthly_limit = m.get("monthly_token_limit", 0) or 0
        if daily_limit > 0 or monthly_limit > 0:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            day_usage = db.execute(
                "SELECT SUM(total_tokens) as total FROM model_usage WHERE model_id=? AND date=?",
                (m["id"], today),
            )
            day_total = (day_usage[0]["total"] or 0) if day_usage else 0
            if daily_limit > 0 and day_total >= daily_limit * 0.8:
                budget_alerts.append({
                    "model": m.get("name", m["id"]),
                    "type": "daily",
                    "used": day_total,
                    "limit": daily_limit,
                    "pct": round(day_total / daily_limit * 100, 1),
                })

    ctx["usage_rows"] = usage_rows
    ctx["budget_alerts"] = budget_alerts

    return render(request, "pages/model_usage.html", ctx)
