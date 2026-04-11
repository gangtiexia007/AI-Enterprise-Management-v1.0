"""
Bitable (飞书多维表格) config, sync, data preview, daily-row generation, CSV import.
"""
from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, date, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
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


# ──── Daily row generation (每日运营数据) ────

def _extract_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(
            (x.get("text") or x.get("name") or "") if isinstance(x, dict) else str(x)
            for x in v
        )
    return str(v)


@router.get("/daily-ops/stores")
def list_known_stores(db: Session = Depends(get_db)):
    """Return distinct store+platform pairs from existing 每日运营数据 records."""
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    tid = (table_map.get("每日运营数据") or "").strip()
    if not token or not tid:
        raise HTTPException(status_code=400, detail="每日运营数据表未配置")

    items = bitable_client.list_all_record_ids(token, tid, max_pages=20)
    seen: dict[str, str] = {}
    for rec in items:
        fields = rec.get("fields") or {}
        store = _extract_text(fields.get("店铺名称")).strip()
        platform = _extract_text(fields.get("平台")).strip()
        if store and store not in seen:
            seen[store] = platform
    stores = [{"store": s, "platform": p} for s, p in sorted(seen.items())]
    return {"stores": stores, "count": len(stores)}


@router.post("/daily-ops/generate")
def generate_daily_rows(
    target_date: Optional[str] = Query(None, description="yyyy-MM-dd, default today"),
    db: Session = Depends(get_db),
):
    """Create blank rows in 每日运营数据 for all known stores for the given date."""
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    tid = (table_map.get("每日运营数据") or "").strip()
    if not token or not tid:
        raise HTTPException(status_code=400, detail="每日运营数据表未配置")

    if target_date:
        try:
            d = datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，需 yyyy-MM-dd")
    else:
        d = date.today()

    date_ms = int(datetime.combine(d, datetime.min.time()).timestamp()) * 1000

    items = bitable_client.list_all_record_ids(token, tid, max_pages=20)
    stores: dict[str, str] = {}
    existing_today: set[str] = set()
    for rec in items:
        fields = rec.get("fields") or {}
        store = _extract_text(fields.get("店铺名称")).strip()
        platform = _extract_text(fields.get("平台")).strip()
        if store:
            stores[store] = platform
        rec_date = fields.get("日期")
        if rec_date is not None:
            ts = rec_date / 1000 if isinstance(rec_date, (int, float)) and rec_date > 1e12 else (rec_date if isinstance(rec_date, (int, float)) else 0)
            if ts:
                rec_d = datetime.fromtimestamp(ts).date()
                if rec_d == d and store:
                    existing_today.add(store)

    if not stores:
        return {"created": 0, "message": "没有找到已有店铺记录，请先手动录入至少一天的数据以建立店铺清单"}

    to_create = []
    for store, platform in sorted(stores.items()):
        if store in existing_today:
            continue
        row: dict[str, Any] = {
            "店铺名称": store,
            "日期": date_ms,
        }
        if platform:
            row["平台"] = platform
        to_create.append({"fields": row})

    if not to_create:
        return {"created": 0, "message": f"{d.isoformat()} 的行已存在，无需重复生成", "date": d.isoformat()}

    batch_size = 100
    created = 0
    for i in range(0, len(to_create), batch_size):
        batch = to_create[i:i + batch_size]
        try:
            bitable_client.batch_create_records(token, tid, batch)
            created += len(batch)
        except Exception as e:
            return {"created": created, "error": str(e), "date": d.isoformat()}
        if i + batch_size < len(to_create):
            time.sleep(0.5)

    bitable_client.invalidate(tid)
    return {
        "created": created,
        "date": d.isoformat(),
        "stores": [r["fields"]["店铺名称"] for r in to_create],
        "message": f"已为 {created} 个店铺生成 {d.isoformat()} 的空行，去飞书填数字即可",
    }


# ──── CSV Import ────

_FIELD_ALIASES = {
    "店铺": "店铺名称", "店铺名": "店铺名称", "store": "店铺名称",
    "date": "日期", "日期": "日期",
    "platform": "平台", "平台": "平台",
    "orders": "出单量", "出单量": "出单量", "出单": "出单量", "订单数": "出单量",
    "impressions": "曝光量", "曝光量": "曝光量", "曝光": "曝光量",
    "clicks": "点击量", "点击量": "点击量", "点击": "点击量",
    "aov": "客单价(元)", "客单价": "客单价(元)", "客单价(元)": "客单价(元)",
    "新上架": "新上架数", "新上架数": "新上架数", "上架数": "新上架数",
    "备注": "备注", "note": "备注",
}

_NUMERIC_FIELDS = {"出单量", "曝光量", "点击量", "客单价(元)", "新上架数"}


@router.post("/daily-ops/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    target_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Import CSV/TSV into 每日运营数据. Column headers are fuzzy-matched."""
    from harness.bitable_client import bitable_client

    token, table_map, _c = _load_config(db)
    tid = (table_map.get("每日运营数据") or "").strip()
    if not token or not tid:
        raise HTTPException(status_code=400, detail="每日运营数据表未配置")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")

    delimiter = "\t" if "\t" in text.split("\n", 1)[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    date_ms = None
    if target_date:
        try:
            d = datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
            date_ms = int(datetime.combine(d, datetime.min.time()).timestamp()) * 1000
        except ValueError:
            pass

    records_to_create: list[dict] = []
    skipped = 0

    for row in reader:
        fields: dict[str, Any] = {}
        for csv_col, value in row.items():
            if csv_col is None or value is None:
                continue
            col_clean = csv_col.strip().lower()
            mapped = _FIELD_ALIASES.get(col_clean) or _FIELD_ALIASES.get(csv_col.strip())
            if not mapped:
                for alias, target in _FIELD_ALIASES.items():
                    if alias in col_clean:
                        mapped = target
                        break
            if not mapped:
                continue

            val = value.strip()
            if not val:
                continue

            if mapped in _NUMERIC_FIELDS:
                val_clean = val.replace(",", "").replace("¥", "").replace("$", "").replace("₱", "").strip()
                try:
                    fields[mapped] = float(val_clean) if "." in val_clean else int(val_clean)
                except ValueError:
                    continue
            elif mapped == "日期":
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        dt = datetime.strptime(val[:10], fmt)
                        fields["日期"] = int(dt.timestamp()) * 1000
                        break
                    except ValueError:
                        continue
            else:
                fields[mapped] = val

        if date_ms and "日期" not in fields:
            fields["日期"] = date_ms

        if "店铺名称" not in fields:
            skipped += 1
            continue

        records_to_create.append({"fields": fields})

    if not records_to_create:
        return {"imported": 0, "skipped": skipped, "message": "没有可导入的行，请检查 CSV 是否包含「店铺名称」列"}

    batch_size = 100
    imported = 0
    for i in range(0, len(records_to_create), batch_size):
        batch = records_to_create[i:i + batch_size]
        try:
            bitable_client.batch_create_records(token, tid, batch)
            imported += len(batch)
        except Exception as e:
            return {"imported": imported, "skipped": skipped, "error": str(e)}
        if i + batch_size < len(records_to_create):
            time.sleep(0.5)

    bitable_client.invalidate(tid)
    return {
        "imported": imported,
        "skipped": skipped,
        "message": f"成功导入 {imported} 行到每日运营数据表",
    }
