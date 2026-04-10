"""
Feishu Bitable (多维表格) HTTP client with in-memory cache and CRUD helpers.

Uses tenant_access_token from FeishuClient (same app as IM).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

import httpx

from harness.feishu_client import FEISHU_BASE, feishu_client

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 300
_MAX_AGG_PAGES = 50
_PAGE_SIZE = 500


def _cache_key(table_id: str, extra: str) -> str:
    h = hashlib.sha256(extra.encode("utf-8")).hexdigest()[:16]
    return f"{table_id}:{h}"


class BitableClient:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._last_sync: dict[str, float] = {}

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {feishu_client._get_tenant_token()}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        retry_once: bool = True,
    ) -> dict:
        url = f"{FEISHU_BASE}{path}"
        with httpx.Client(timeout=30) as client:
            resp = client.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
            )
            data = resp.json()
        if data.get("code") != 0:
            msg = data.get("msg", str(data))
            # Token invalid — clear Feishu cache and retry once
            if retry_once and ("99991663" in str(data) or "token" in msg.lower()):
                feishu_client._token = None
                feishu_client._token_expires = 0
                return self._request(method, path, params=params, json_body=json_body, retry_once=False)
            raise RuntimeError(f"Bitable API error: {msg}")
        return data.get("data") or {}

    def invalidate(self, table_id: str) -> None:
        prefix = f"{table_id}:"
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            del self._cache[k]

    def mark_synced(self, alias: str) -> None:
        self._last_sync[alias] = time.time()

    def last_sync_ts(self, alias: str) -> Optional[float]:
        return self._last_sync.get(alias)

    def list_tables(self, app_token: str) -> list[dict]:
        out: list[dict] = []
        page_token: Optional[str] = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            data = self._request("GET", f"/bitable/v1/apps/{app_token}/tables", params=params)
            items = data.get("items") or []
            for it in items:
                out.append(
                    {
                        "table_id": it.get("table_id"),
                        "name": it.get("name"),
                        "revision": it.get("revision"),
                    }
                )
            page_token = data.get("page_token")
            if not page_token:
                break
        return out

    def get_table_fields(self, app_token: str, table_id: str) -> list[dict]:
        data = self._request("GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields")
        return data.get("items") or []

    def list_records(
        self,
        app_token: str,
        table_id: str,
        *,
        filter_expr: Optional[str] = None,
        sort: Optional[list] = None,
        page_token: Optional[str] = None,
        page_size: int = _PAGE_SIZE,
        use_cache: bool = False,
        cache_extra: str = "",
    ) -> dict:
        extra = json.dumps(
            {"f": filter_expr, "s": sort, "pt": page_token, "ps": page_size, "e": cache_extra},
            sort_keys=True,
            default=str,
        )
        ck = _cache_key(table_id, extra)
        if use_cache and ck in self._cache:
            ts, val = self._cache[ck]
            if time.time() - ts < CACHE_TTL_SEC:
                return val
        params: dict[str, Any] = {"page_size": min(page_size, 500)}
        if page_token:
            params["page_token"] = page_token
        if filter_expr:
            params["filter"] = filter_expr
        if sort:
            params["sort"] = json.dumps(sort)
        data = self._request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            params=params,
        )
        result = {
            "items": data.get("items") or [],
            "page_token": data.get("page_token"),
            "total": data.get("total"),
        }
        if use_cache:
            self._cache[ck] = (time.time(), result)
        return result

    def search_records(
        self,
        app_token: str,
        table_id: str,
        *,
        filter_info: Optional[dict] = None,
        sort: Optional[list] = None,
        page_token: Optional[str] = None,
        page_size: int = 500,
    ) -> dict:
        body: dict[str, Any] = {"page_size": min(page_size, 500)}
        if page_token:
            body["page_token"] = page_token
        if filter_info:
            body["filter"] = filter_info
        if sort:
            body["sort"] = sort
        data = self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
            json_body=body,
        )
        return {
            "items": data.get("items") or [],
            "page_token": data.get("page_token"),
            "total": data.get("total"),
        }

    def get_record(self, app_token: str, table_id: str, record_id: str) -> dict:
        data = self._request(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
        )
        return data.get("record") or data

    def create_record(self, app_token: str, table_id: str, fields: dict) -> dict:
        data = self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json_body={"fields": fields},
        )
        self.invalidate(table_id)
        return data.get("record") or data

    def update_record(self, app_token: str, table_id: str, record_id: str, fields: dict) -> dict:
        data = self._request(
            "PUT",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            json_body={"fields": fields},
        )
        self.invalidate(table_id)
        return data.get("record") or data

    def batch_create_records(self, app_token: str, table_id: str, records: list[dict]) -> dict:
        """records: list of { \"fields\": {...} }"""
        data = self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            json_body={"records": records},
        )
        self.invalidate(table_id)
        return data

    def list_all_record_ids(
        self,
        app_token: str,
        table_id: str,
        *,
        max_pages: int = _MAX_AGG_PAGES,
    ) -> list[dict]:
        """Fetch records with fields for local aggregation (bounded pages)."""
        all_items: list[dict] = []
        page_token: Optional[str] = None
        pages = 0
        while pages < max_pages:
            chunk = self.list_records(
                app_token,
                table_id,
                page_token=page_token,
                page_size=_PAGE_SIZE,
                use_cache=False,
            )
            items = chunk.get("items") or []
            all_items.extend(items)
            page_token = chunk.get("page_token")
            pages += 1
            if not page_token:
                break
        return all_items

    def aggregate(
        self,
        app_token: str,
        table_id: str,
        field_name: str,
        func: str,
        *,
        max_pages: int = _MAX_AGG_PAGES,
    ) -> dict:
        """
        func: SUM | AVG | COUNT | MIN | MAX over numeric-like field values in records.
        field_name: Bitable field name as returned in record['fields'].
        """
        items = self.list_all_record_ids(app_token, table_id, max_pages=max_pages)
        values: list[float] = []
        for rec in items:
            fields = rec.get("fields") or {}
            v = fields.get(field_name)
            if v is None:
                continue
            if isinstance(v, list) and v:
                v = v[0].get("text") if isinstance(v[0], dict) else v[0]
            try:
                if isinstance(v, (int, float)):
                    values.append(float(v))
                elif isinstance(v, str) and v.strip():
                    values.append(float(v.replace(",", "")))
            except (TypeError, ValueError):
                continue
        n = len(values)
        if func.upper() == "COUNT":
            return {"func": "COUNT", "field": field_name, "count": n}
        if not values:
            return {"func": func, "field": field_name, "result": None, "note": "no numeric values"}
        if func.upper() == "SUM":
            return {"func": "SUM", "field": field_name, "result": sum(values), "count": n}
        if func.upper() == "AVG":
            return {"func": "AVG", "field": field_name, "result": sum(values) / n, "count": n}
        if func.upper() == "MIN":
            return {"func": "MIN", "field": field_name, "result": min(values), "count": n}
        if func.upper() == "MAX":
            return {"func": "MAX", "field": field_name, "result": max(values), "count": n}
        return {"error": f"unknown func {func}", "field": field_name}


bitable_client = BitableClient()
