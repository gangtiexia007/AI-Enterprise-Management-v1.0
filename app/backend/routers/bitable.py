"""
Bitable (飞书多维表格) config, sync, and data preview APIs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Setting
from schemas import (
    BitableConfigOut,
    BitableConfigUpdate,
    BitableSyncResult,
    BitableTableMetaOut,
    BitableTableOverview,
)

router = APIRouter()

# Seed aliases shown only when user has NO config at all yet.
# Category field is kept for DataCenter color-coding but is user-editable via UI.
_SEED_ALIASES: list[tuple[str, str]] = [
    ("员工表", "A"),
    ("店铺表", "A"),
    ("产品表", "A"),
    ("销售数据表", "B"),
    ("财务数据表", "B"),
    ("任务表", "C"),
    ("目标表", "C"),
    ("KPI表", "C"),
    ("反馈记录表", "C"),
    ("催办记录表", "C"),
]
_SEED_MAP: dict[str, str] = {a: cat for a, cat in _SEED_ALIASES}


def _get_setting(db: Session, key: str, default: str = "") -> str:
    s = db.query(Setting).filter(Setting.key == key).first()
    return s.value if s else default


def _upsert_setting(db: Session, key: str, value: str) -> None:
    s = db.query(Setting).filter(Setting.key == key).first()
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def _load_config(db: Session) -> tuple[str, dict[str, str], dict[str, str]]:
    """Returns (base_token, table_map {alias->table_id}, category_map {alias->cat})."""
    token = _get_setting(db, "bitable_base_token", "")
    raw_map = _get_setting(db, "bitable_table_map", "")
    raw_cat = _get_setting(db, "bitable_category_map", "")

    # table_map: alias -> table_id
    try:
        table_map: dict[str, str] = json.loads(raw_map) if raw_map else {}
        if not isinstance(table_map, dict):
            table_map = {}
    except json.JSONDecodeError:
        table_map = {}

    # category_map: alias -> A/B/C (user-editable, default from seed)
    try:
        cat_map: dict[str, str] = json.loads(raw_cat) if raw_cat else {}
        if not isinstance(cat_map, dict):
            cat_map = {}
    except json.JSONDecodeError:
        cat_map = {}

    # If brand-new install with zero config, seed with defaults
    if not raw_map and not raw_cat:
        for alias, cat in _SEED_ALIASES:
            table_map.setdefault(alias, "")
            cat_map.setdefault(alias, cat)

    # Backfill category for any alias missing it
    for alias in table_map:
        cat_map.setdefault(alias, _SEED_MAP.get(alias, "B"))

    return token, table_map, cat_map


def _table_id_for_alias(table_map: dict[str, str], alias: str) -> str:
    tid = (table_map.get(alias) or "").strip()
    if not tid:
        raise HTTPException(status_code=400, detail=f"表别名未映射: {alias}")
    return tid


def _iso_ts(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@router.get("/config", response_model=BitableConfigOut)
def get_config(db: Session = Depends(get_db)):
    token, table_map, cat_map = _load_config(db)
    return BitableConfigOut(base_token=token, table_map=table_map, category_map=cat_map)


@router.put("/config", response_model=BitableConfigOut)
def update_config(body: BitableConfigUpdate, db: Session = Depends(get_db)):
    if body.base_token is not None:
        _upsert_setting(db, "bitable_base_token", body.base_token)
    if body.table_map is not None:
        _upsert_setting(db, "bitable_table_map", json.dumps(body.table_map, ensure_ascii=False))
    if body.category_map is not None:
        _upsert_setting(db, "bitable_category_map", json.dumps(body.category_map, ensure_ascii=False))
    token, table_map, cat_map = _load_config(db)
    return BitableConfigOut(base_token=token, table_map=table_map, category_map=cat_map)


@router.post("/test-connection")
def test_connection(db: Session = Depends(get_db)):
    from harness.bitable_client import bitable_client

    token, _, _c = _load_config(db)
    if not token:
        raise HTTPException(status_code=400, detail="未配置 bitable_base_token")
    try:
        tables = bitable_client.list_tables(token)
        return {"ok": True, "table_count": len(tables), "sample": tables[:5]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/tables", response_model=list[BitableTableMetaOut])
def list_tables(db: Session = Depends(get_db)):
    from harness.bitable_client import bitable_client

    token, _, _c = _load_config(db)
    if not token:
        raise HTTPException(status_code=400, detail="未配置 bitable_base_token")
    try:
        raw = bitable_client.list_tables(token)
        return [BitableTableMetaOut(**x) for x in raw]
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/overview", response_model=list[BitableTableOverview])
def overview(db: Session = Depends(get_db)):
    from harness.bitable_client import bitable_client

    token, table_map, cat_map = _load_config(db)
    out: list[BitableTableOverview] = []
    for alias, tid_raw in table_map.items():
        cat = cat_map.get(alias, "B")
        tid = (tid_raw or "").strip()
        count = 0
        if token and tid:
            try:
                data = bitable_client.list_records(
                    token,
                    tid,
                    page_size=1,
                    use_cache=True,
                    cache_extra="overview_count",
                )
                total = data.get("total")
                if total is not None:
                    count = int(total)
                else:
                    # Fallback: one page count
                    items = data.get("items") or []
                    count = len(items)
            except Exception:
                count = 0
        ls = bitable_client.last_sync_ts(alias)
        out.append(
            BitableTableOverview(
                alias=alias,
                category=cat,
                table_id=tid,
                record_count=count,
                last_sync_at=_iso_ts(ls),
            )
        )
    return out


@router.post("/sync", response_model=list[BitableSyncResult])
def sync_all(db: Session = Depends(get_db)):
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    if not token:
        raise HTTPException(status_code=400, detail="未配置 bitable_base_token")
    results: list[BitableSyncResult] = []
    for alias, tid_raw in table_map.items():
        tid = (tid_raw or "").strip()
        if not tid:
            results.append(BitableSyncResult(ok=False, alias=alias, detail="未映射 table_id"))
            continue
        try:
            bitable_client.invalidate(tid)
            bitable_client.list_records(
                token,
                tid,
                page_size=100,
                use_cache=True,
                cache_extra="full_sync_seed",
            )
            bitable_client.mark_synced(alias)
            results.append(
                BitableSyncResult(ok=True, alias=alias, detail="缓存已刷新", invalidated_tables=[tid])
            )
        except Exception as e:
            results.append(BitableSyncResult(ok=False, alias=alias, detail=str(e)))
    return results


@router.post("/sync/{alias}", response_model=BitableSyncResult)
def sync_one(alias: str, db: Session = Depends(get_db)):
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    if not token:
        raise HTTPException(status_code=400, detail="未配置 bitable_base_token")
    tid = _table_id_for_alias(table_map, alias)
    try:
        bitable_client.invalidate(tid)
        bitable_client.list_records(
            token,
            tid,
            page_size=100,
            use_cache=True,
            cache_extra="single_sync_seed",
        )
        bitable_client.mark_synced(alias)
        return BitableSyncResult(ok=True, alias=alias, detail="缓存已刷新", invalidated_tables=[tid])
    except Exception as e:
        return BitableSyncResult(ok=False, alias=alias, detail=str(e))


@router.get("/tables/{alias}/stats")
def table_stats(alias: str, db: Session = Depends(get_db)):
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    if not token:
        raise HTTPException(status_code=400, detail="未配置 bitable_base_token")
    tid = _table_id_for_alias(table_map, alias)
    try:
        data = bitable_client.list_records(token, tid, page_size=1, use_cache=True)
        total = data.get("total")
        return {
            "alias": alias,
            "table_id": tid,
            "total": total,
            "last_sync_at": _iso_ts(bitable_client.last_sync_ts(alias)),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/tables/{alias}/records")
def table_records(
    alias: str,
    db: Session = Depends(get_db),
    page_token: Optional[str] = Query(None),
    page_size: int = Query(50, ge=1, le=500),
    q: Optional[str] = Query(None, description="简单关键词：在记录 fields 的字符串值中子串匹配"),
):
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    if not token:
        raise HTTPException(status_code=400, detail="未配置 bitable_base_token")
    tid = _table_id_for_alias(table_map, alias)
    try:
        data = bitable_client.list_records(
            token,
            tid,
            page_token=page_token,
            page_size=page_size,
            use_cache=not q,
            cache_extra=f"page:{page_token}:{page_size}",
        )
        items: list[dict[str, Any]] = data.get("items") or []
        if q:
            qn = q.strip().lower()
            filtered = []
            for rec in items:
                blob = json.dumps(rec.get("fields") or {}, ensure_ascii=False).lower()
                if qn in blob:
                    filtered.append(rec)
            items = filtered
        return {
            "items": items,
            "page_token": data.get("page_token"),
            "total": data.get("total"),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
