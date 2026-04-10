"""Builtin skills for Feishu Bitable (多维表格) — business data read/write."""
from __future__ import annotations

import json
from typing import Any, Optional

from harness.skill_registry import tool, ToolResult


def _session_db(db_session):
    if db_session is not None:
        return db_session, False
    from database import SessionLocal

    return SessionLocal(), True


def _bitable_settings(db) -> tuple[str, dict[str, str]]:
    from models import Setting

    def gs(key: str, default: str = "") -> str:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default

    token = gs("bitable_base_token", "")
    raw = gs("bitable_table_map", "{}")
    try:
        m = json.loads(raw) if raw else {}
        if not isinstance(m, dict):
            m = {}
    except json.JSONDecodeError:
        m = {}
    return token, m


def _tid(table_map: dict[str, str], alias: str) -> Optional[str]:
    tid = (table_map.get(alias) or "").strip()
    return tid or None


def _flatten_field_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts = []
        for x in v:
            if isinstance(x, dict):
                parts.append(x.get("text") or x.get("name") or json.dumps(x, ensure_ascii=False))
            else:
                parts.append(str(x))
        return " ".join(parts)
    return str(v)


def _record_match(rec: dict, needle: str) -> bool:
    needle = needle.lower()
    fields = rec.get("fields") or {}
    blob = json.dumps(fields, ensure_ascii=False).lower()
    return needle in blob


@tool(
    name="query_bitable",
    description="从飞书多维表格按表别名查询记录。表别名如：员工表、店铺表、销售数据表、财务数据表等。可选关键词在整行字段中文本中子串匹配。",
    parameters={
        "type": "object",
        "properties": {
            "table_alias": {"type": "string", "description": "表中文别名，如 员工表 / 销售数据表"},
            "keyword": {"type": "string", "description": "可选，关键词过滤"},
            "limit": {"type": "integer", "description": "最多返回条数，默认 20"},
        },
        "required": ["table_alias"],
    },
    permission_level=0,
)
async def query_bitable(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        if not token:
            return ToolResult(success=False, error="未配置多维表格 base_token，请在设置中填写。")
        alias = kwargs.get("table_alias") or ""
        tid = _tid(table_map, alias)
        if not tid:
            return ToolResult(success=False, error=f"表「{alias}」未映射 table_id。")
        limit = int(kwargs.get("limit") or 20)
        limit = max(1, min(limit, 100))
        kw = (kwargs.get("keyword") or "").strip()
        items: list[dict] = []
        page_token = None
        while len(items) < limit:
            chunk = bitable_client.list_records(
                token,
                tid,
                page_token=page_token,
                page_size=min(500, limit * 2),
                use_cache=True,
                cache_extra=f"skill_query:{kw}:{page_token}",
            )
            batch = chunk.get("items") or []
            for rec in batch:
                if kw and not _record_match(rec, kw):
                    continue
                rid = rec.get("record_id")
                items.append({"record_id": rid, "fields": rec.get("fields") or {}})
                if len(items) >= limit:
                    break
            page_token = chunk.get("page_token")
            if not page_token:
                break
        return ToolResult(success=True, data={"table": alias, "count": len(items), "items": items})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


@tool(
    name="write_bitable",
    description="向飞书多维表格指定别名表新增一行记录。fields 为 JSON 对象，键为列名、值为单元格内容（与多维表格字段名一致）。",
    parameters={
        "type": "object",
        "properties": {
            "table_alias": {"type": "string"},
            "fields_json": {"type": "string", "description": "JSON 字符串，例如 {\"姓名\":\"张三\",\"备注\":\"催办\"}"},
        },
        "required": ["table_alias", "fields_json"],
    },
    permission_level=2,
)
async def write_bitable(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        if not token:
            return ToolResult(success=False, error="未配置多维表格 base_token。")
        alias = kwargs.get("table_alias") or ""
        tid = _tid(table_map, alias)
        if not tid:
            return ToolResult(success=False, error=f"表「{alias}」未映射 table_id。")
        raw = kwargs.get("fields_json") or "{}"
        try:
            fields = json.loads(raw)
        except json.JSONDecodeError as e:
            return ToolResult(success=False, error=f"fields_json 非合法 JSON: {e}")
        if not isinstance(fields, dict):
            return ToolResult(success=False, error="fields_json 必须是 JSON 对象")
        rec = bitable_client.create_record(token, tid, fields)
        return ToolResult(success=True, data={"table": alias, "record": rec})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


def _numeric_from_fields(fields: dict, key: str) -> Optional[float]:
    v = fields.get(key)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = _flatten_field_value(v).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


@tool(
    name="sales_summary",
    description="汇总「销售数据表」中的数值字段（需在多维表格中有对应列名）。可指定店铺列名、GMV 列名、日期列名及店铺关键词、开始/结束日期（字符串匹配）。",
    parameters={
        "type": "object",
        "properties": {
            "store_field": {"type": "string", "description": "店铺字段名，默认 店铺"},
            "gmv_field": {"type": "string", "description": "GMV/销售额字段名，默认 GMV"},
            "date_field": {"type": "string", "description": "日期字段名，默认 日期"},
            "store_keyword": {"type": "string", "description": "可选，店铺名称包含该关键词"},
            "date_from": {"type": "string", "description": "可选，日期起始（子串）"},
            "date_to": {"type": "string", "description": "可选，日期结束（子串）"},
        },
        "required": [],
    },
    permission_level=0,
)
async def sales_summary(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        alias = "销售数据表"
        tid = _tid(table_map, alias)
        if not token or not tid:
            return ToolResult(success=False, error="销售数据表未配置或 base_token 缺失。")
        sf = kwargs.get("store_field") or "店铺"
        gf = kwargs.get("gmv_field") or "GMV"
        df = kwargs.get("date_field") or "日期"
        sk = (kwargs.get("store_keyword") or "").strip().lower()
        d0 = (kwargs.get("date_from") or "").strip()
        d1 = (kwargs.get("date_to") or "").strip()
        rows = bitable_client.list_all_record_ids(token, tid, max_pages=30)
        total_gmv = 0.0
        n = 0
        for rec in rows:
            fields = rec.get("fields") or {}
            if sk:
                sv = _flatten_field_value(fields.get(sf)).lower()
                if sk not in sv:
                    continue
            if d0 or d1:
                dv = _flatten_field_value(fields.get(df))
                if d0 and d0 not in dv:
                    continue
                if d1 and d1 not in dv:
                    continue
            g = _numeric_from_fields(fields, gf)
            if g is not None:
                total_gmv += g
                n += 1
        return ToolResult(
            success=True,
            data={"table": alias, "matched_rows": n, "sum_gmv": total_gmv, "gmv_field": gf},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


@tool(
    name="store_ranking",
    description="按「销售数据表」中店铺维度汇总 GMV 并排序，返回前几名店铺。",
    parameters={
        "type": "object",
        "properties": {
            "store_field": {"type": "string", "description": "默认 店铺"},
            "gmv_field": {"type": "string", "description": "默认 GMV"},
            "top_n": {"type": "integer", "description": "默认 5"},
        },
        "required": [],
    },
    permission_level=0,
)
async def store_ranking(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        tid = _tid(table_map, "销售数据表")
        if not token or not tid:
            return ToolResult(success=False, error="销售数据表未配置。")
        sf = kwargs.get("store_field") or "店铺"
        gf = kwargs.get("gmv_field") or "GMV"
        top_n = int(kwargs.get("top_n") or 5)
        top_n = max(1, min(top_n, 20))
        rows = bitable_client.list_all_record_ids(token, tid, max_pages=30)
        agg: dict[str, float] = {}
        for rec in rows:
            fields = rec.get("fields") or {}
            name = _flatten_field_value(fields.get(sf)).strip() or "(未命名店铺)"
            g = _numeric_from_fields(fields, gf)
            if g is None:
                continue
            agg[name] = agg.get(name, 0.0) + g
        ranked = sorted(agg.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return ToolResult(success=True, data={"ranking": [{"store": a, "gmv": b} for a, b in ranked]})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()


@tool(
    name="employee_lookup",
    description="在「员工表」中按姓名或关键词查找员工记录（子串匹配所有字段）。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "姓名或关键词"},
            "limit": {"type": "integer", "description": "默认 10"},
        },
        "required": ["keyword"],
    },
    permission_level=0,
)
async def employee_lookup(db_session=None, **kwargs) -> ToolResult:
    kwargs["table_alias"] = "员工表"
    kwargs["limit"] = kwargs.get("limit") or 10
    return await query_bitable(db_session=db_session, **kwargs)


@tool(
    name="finance_summary",
    description="汇总「财务数据表」中收入、成本、毛利等数值列（列名可配置，默认 收入/成本/毛利润）。",
    parameters={
        "type": "object",
        "properties": {
            "revenue_field": {"type": "string", "description": "默认 收入"},
            "cost_field": {"type": "string", "description": "默认 成本"},
            "profit_field": {"type": "string", "description": "默认 毛利润"},
            "period_keyword": {"type": "string", "description": "可选，在整行文本中匹配期间"},
        },
        "required": [],
    },
    permission_level=0,
)
async def finance_summary(db_session=None, **kwargs) -> ToolResult:
    from harness.bitable_client import bitable_client

    db, close = _session_db(db_session)
    try:
        token, table_map = _bitable_settings(db)
        tid = _tid(table_map, "财务数据表")
        if not token or not tid:
            return ToolResult(success=False, error="财务数据表未配置。")
        rf = kwargs.get("revenue_field") or "收入"
        cf = kwargs.get("cost_field") or "成本"
        pf = kwargs.get("profit_field") or "毛利润"
        pk = (kwargs.get("period_keyword") or "").strip().lower()
        rows = bitable_client.list_all_record_ids(token, tid, max_pages=30)
        sum_r = sum_c = sum_p = 0.0
        nr = nc = np = 0
        for rec in rows:
            fields = rec.get("fields") or {}
            if pk:
                blob = json.dumps(fields, ensure_ascii=False).lower()
                if pk not in blob:
                    continue
            rv = _numeric_from_fields(fields, rf)
            cv = _numeric_from_fields(fields, cf)
            pv = _numeric_from_fields(fields, pf)
            if rv is not None:
                sum_r += rv
                nr += 1
            if cv is not None:
                sum_c += cv
                nc += 1
            if pv is not None:
                sum_p += pv
                np += 1
        margin = (sum_p / sum_r * 100) if sum_r else None
        return ToolResult(
            success=True,
            data={
                "sum_revenue": sum_r,
                "sum_cost": sum_c,
                "sum_profit": sum_p,
                "rows_with_revenue": nr,
                "approx_margin_pct": round(margin, 2) if margin is not None else None,
            },
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
    finally:
        if close:
            db.close()
