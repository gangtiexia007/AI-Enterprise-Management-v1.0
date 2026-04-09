"""External data webhook — receive structured data from ERP/shop platforms."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import JSONResponse

from app.core.database import Database, new_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/data")
async def receive_external_data(
    request: Request,
    x_source: str = Header("unknown", alias="X-Source"),
    x_team_id: str = Header("", alias="X-Team-Id"),
    x_api_key: str = Header("", alias="X-API-Key"),
):
    """Receive a JSON payload from an external system and store it.

    Expected body format:
    {
        "data_type": "orders" | "financial" | "inventory" | "custom",
        "records": [...],      # Array of data records
        "metadata": {...}      # Optional metadata
    }
    """
    db = Database.get_instance()

    if x_team_id:
        team = db.get_by_id("teams", x_team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        expected_key = (team.get("webhook_api_key") or "").strip()
        if expected_key and x_api_key != expected_key:
            raise HTTPException(status_code=403, detail="Invalid API key")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    data_type = body.get("data_type", "custom")
    records = body.get("records", [])
    metadata = body.get("metadata", {})

    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="'records' must be an array")

    db.execute("""
        CREATE TABLE IF NOT EXISTS webhook_data (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            data_type TEXT NOT NULL DEFAULT 'custom',
            record_count INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'received',
            processed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    record_id = new_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    db.insert("webhook_data", {
        "id": record_id,
        "team_id": x_team_id,
        "source": x_source,
        "data_type": data_type,
        "record_count": len(records),
        "payload_json": json.dumps(body, ensure_ascii=False),
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "status": "received",
        "created_at": now,
    })

    try:
        from app.infra.eventbus import EventBus
        bus = EventBus.get_instance()
        bus.emit_nowait("webhook.data_received", {
            "webhook_id": record_id,
            "team_id": x_team_id,
            "source": x_source,
            "data_type": data_type,
            "record_count": len(records),
        })
    except Exception:
        pass

    logger.info("Webhook data received: source=%s type=%s records=%d", x_source, data_type, len(records))

    return JSONResponse({
        "status": "received",
        "id": record_id,
        "record_count": len(records),
    })


@router.get("/data")
async def list_webhook_data(request: Request):
    """List recent webhook data receipts."""
    db = Database.get_instance()
    try:
        rows = db.execute(
            "SELECT id, team_id, source, data_type, record_count, status, created_at "
            "FROM webhook_data ORDER BY created_at DESC LIMIT 100"
        )
    except Exception:
        rows = []
    return JSONResponse({"items": rows})
