"""F13 Feishu Bitable Skill — create tables, append records, query records in Feishu Bitable.

Uses Feishu Open API directly via httpx (not lark-cli) for maximum reliability.
Requires a valid Feishu App with bitable permissions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.enums import PermissionLevel
from app.skills.sdk import ToolContext, tool

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


async def _get_bitable_token(team_id: str = "") -> str:
    """Get a tenant access token for Bitable API calls."""
    if team_id:
        from app.skills.builtin.feishu_im import _get_bot_credentials, _get_tenant_access_token
        creds = _get_bot_credentials(team_id)
        return await _get_tenant_access_token(creds.get("app_id", ""), creds.get("app_secret", ""))
    else:
        from app.core.config import get_config
        from app.skills.builtin.feishu_im import _get_tenant_access_token
        cfg = get_config()
        return await _get_tenant_access_token(cfg.feishu_app_id, cfg.feishu_app_secret)


@tool(
    description="在飞书多维表格中创建数据表。返回新建的 table_id。",
    permission=PermissionLevel.P2,
)
async def feishu_bitable__create_table(
    ctx: ToolContext,
    app_token: str,
    table_name: str,
    fields: str,
) -> dict[str, Any]:
    """Create a table in a Feishu Bitable app.

    Args:
        app_token: The Bitable app token (from URL: https://xxx.feishu.cn/base/<app_token>)
        table_name: Name of the new table
        fields: JSON string of field definitions, e.g. [{"field_name":"订单号","type":1},{"field_name":"金额","type":2}]
                Field types: 1=Text, 2=Number, 3=SingleSelect, 4=MultiSelect, 5=DateTime, 7=Checkbox, 11=Person, 13=Phone, 15=Link, 17=Attachment, 18=Link, 19=Formula, 20=DuplexLink, 22=UpdatedTime, 23=CreatedTime
    """
    try:
        field_list = json.loads(fields) if isinstance(fields, str) else fields
    except json.JSONDecodeError:
        return {"error": "fields must be valid JSON array"}

    token = await _get_bitable_token(ctx.team_id)

    url = f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables"
    body = {
        "table": {
            "name": table_name,
            "fields": field_list,
        }
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

    if data.get("code") != 0:
        return {"error": f"Feishu API error: {data.get('msg', 'unknown')} (code={data.get('code')})"}

    table_id = data.get("data", {}).get("table_id", "")
    logger.info("Created Bitable table: %s in app %s", table_id, app_token)
    return {"table_id": table_id, "table_name": table_name}


@tool(
    description="向飞书多维表格追加记录（批量写入）。",
    permission=PermissionLevel.P2,
)
async def feishu_bitable__append_records(
    ctx: ToolContext,
    app_token: str,
    table_id: str,
    records: str,
) -> dict[str, Any]:
    """Append records to a Feishu Bitable table.

    Args:
        app_token: The Bitable app token
        table_id: The table ID to append to
        records: JSON string of records, e.g. [{"fields":{"订单号":"A001","金额":100}}, ...]
    """
    try:
        record_list = json.loads(records) if isinstance(records, str) else records
    except json.JSONDecodeError:
        return {"error": "records must be valid JSON array"}

    if not isinstance(record_list, list):
        return {"error": "records must be a JSON array"}
    if len(record_list) > 500:
        return {"error": f"Feishu Bitable batch limit is 500 records, got {len(record_list)}"}

    token = await _get_bitable_token(ctx.team_id)

    url = f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    body = {"records": record_list}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

    if data.get("code") != 0:
        return {"error": f"Feishu API error: {data.get('msg', 'unknown')} (code={data.get('code')})"}

    created = data.get("data", {}).get("records", [])
    logger.info("Appended %d records to table %s", len(created), table_id)
    return {"appended_count": len(created), "table_id": table_id}


@tool(
    description="查询飞书多维表格中的记录（支持筛选和分页）。",
    permission=PermissionLevel.P1,
)
async def feishu_bitable__query_records(
    ctx: ToolContext,
    app_token: str,
    table_id: str,
    filter_expr: str = "",
    page_size: int = 100,
    page_token: str = "",
) -> dict[str, Any]:
    """Query records from a Feishu Bitable table.

    Args:
        app_token: The Bitable app token
        table_id: The table ID to query
        filter_expr: Optional filter formula, e.g. 'CurrentValue.[订单号]="A001"'
        page_size: Number of records per page (max 500)
        page_token: Pagination token for next page
    """
    token = await _get_bitable_token(ctx.team_id)
    effective_page_size = max(1, min(page_size, 500))

    list_url = f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    params: dict[str, Any] = {"page_size": effective_page_size}
    if filter_expr:
        params["filter"] = filter_expr
    if page_token:
        params["page_token"] = page_token

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(list_url, params=params, headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

    if data.get("code") != 0:
        return {"error": f"Feishu API error: {data.get('msg', 'unknown')} (code={data.get('code')})"}

    items = data.get("data", {}).get("items", [])
    has_more = data.get("data", {}).get("has_more", False)
    next_token = data.get("data", {}).get("page_token", "")
    total = data.get("data", {}).get("total", len(items))

    records = []
    for item in items:
        rec = item.get("fields", {})
        rec["_record_id"] = item.get("record_id", "")
        records.append(rec)

    return {
        "records": records,
        "total": total,
        "has_more": has_more,
        "page_token": next_token,
    }


@tool(
    description="获取飞书多维表格的所有数据表列表。",
    permission=PermissionLevel.P1,
)
async def feishu_bitable__list_tables(
    ctx: ToolContext,
    app_token: str,
) -> dict[str, Any]:
    """List all tables in a Feishu Bitable app.

    Args:
        app_token: The Bitable app token
    """
    token = await _get_bitable_token(ctx.team_id)

    url = f"{FEISHU_API_BASE}/bitable/v1/apps/{app_token}/tables"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

    if data.get("code") != 0:
        return {"error": f"Feishu API error: {data.get('msg', 'unknown')} (code={data.get('code')})"}

    tables = []
    for item in data.get("data", {}).get("items", []):
        tables.append({
            "table_id": item.get("table_id", ""),
            "name": item.get("name", ""),
            "revision": item.get("revision", 0),
        })

    return {"tables": tables, "count": len(tables)}
