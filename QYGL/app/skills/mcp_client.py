"""F15: MCP Client — discover and import tools from external MCP servers.

V1 provides a lightweight import mechanism:

1. Connect to an MCP server endpoint.
2. Call ``tools/list`` to discover available tools.
3. Register each discovered tool into the ``SkillRegistry`` as an MCP skill.
4. Create proxy tool functions that forward calls to the remote server.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.core.enums import PermissionLevel, SkillSource

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class MCPClient:
    """Lightweight MCP client for tool discovery and proxied execution."""

    def __init__(
        self,
        server_url: str,
        api_key: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._tools_cache: list[dict[str, Any]] = []

    # ── Discovery ─────────────────────────────────────────────────

    async def discover_tools(self) -> list[dict[str, Any]]:
        """Call the MCP server's ``tools/list`` endpoint and return tool schemas."""
        headers = self._build_headers()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.server_url}/rpc",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("MCP discovery failed for %s: %s", self.server_url, exc)
            return []

        tools = data.get("result", {}).get("tools", [])
        self._tools_cache = tools
        logger.info("MCP server %s returned %d tools", self.server_url, len(tools))
        return tools

    # ── Proxied Execution ─────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Forward a tool call to the MCP server via ``tools/call``."""
        headers = self._build_headers()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.server_url}/rpc",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("MCP tool call %s failed: %s", tool_name, exc)
            return {"error": str(exc)}

        result = data.get("result", {})
        content_items = result.get("content", [])
        if content_items and isinstance(content_items, list):
            text_parts = [
                c.get("text", "") for c in content_items if c.get("type") == "text"
            ]
            return {"text": "\n".join(text_parts), "raw": content_items}
        return result

    # ── Registration ──────────────────────────────────────────────

    async def register_into_skill_registry(
        self,
        skill_name: str | None = None,
        display_name: str | None = None,
    ) -> None:
        """Discover tools and register them as an MCP skill in the registry."""
        tools = await self.discover_tools()
        if not tools:
            return

        name = skill_name or _derive_skill_name(self.server_url)
        tools_json = [
            {
                "name": f"{name}__{t.get('name', 'unknown')}",
                "description": t.get("description", ""),
                "permission": PermissionLevel.P1.value,
                "parameters": t.get("inputSchema", {}),
                "mcp_original_name": t.get("name", ""),
            }
            for t in tools
        ]

        from app.skills.registry import SkillRegistry
        registry = SkillRegistry.get_instance()
        registry.register_mcp_skill(
            name=name,
            display_name=display_name or name.replace("_", " ").title(),
            tools_json=tools_json,
            config_json={
                "server_url": self.server_url,
                "has_api_key": bool(self.api_key),
            },
        )
        logger.info("Registered MCP skill '%s' with %d tools", name, len(tools_json))

    # ── Internals ─────────────────────────────────────────────────

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _derive_skill_name(url: str) -> str:
    """Create a valid skill name from a URL."""
    import re
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or "mcp"
    name = re.sub(r"[^a-zA-Z0-9]", "_", host).strip("_")
    return f"mcp_{name}"
