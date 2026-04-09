"""MCP (Model Context Protocol) client for external tool servers."""
import json
import logging
from typing import Optional
import httpx
from harness.skill_registry import ToolResult

logger = logging.getLogger(__name__)


class MCPClient:
    """JSON-RPC 2.0 client for MCP tool servers."""

    async def call_tool(
        self,
        endpoint: str,
        tool_name: str,
        params: dict,
        auth_config: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> ToolResult:
        headers = {"Content-Type": "application/json"}
        if auth_config:
            if auth_config.get("type") == "bearer":
                headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
            elif auth_config.get("type") == "api_key":
                headers[auth_config.get("header", "X-API-Key")] = auth_config.get("key", "")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params},
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    return ToolResult(success=False, error=data["error"].get("message", "MCP error"))

                result = data.get("result", {})
                content = result.get("content", [])
                text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return ToolResult(success=True, data="\n".join(text_parts) if text_parts else json.dumps(result, ensure_ascii=False))

        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"MCP server timeout: {endpoint}")
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def list_tools(self, endpoint: str, auth_config: Optional[dict] = None) -> list[dict]:
        headers = {"Content-Type": "application/json"}
        if auth_config and auth_config.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"

        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"MCP list_tools failed: {e}")
            return []

    async def test_connection(self, endpoint: str, auth_config: Optional[dict] = None) -> ToolResult:
        try:
            tools = await self.list_tools(endpoint, auth_config)
            return ToolResult(success=True, data={"message": "连接成功", "tools_count": len(tools), "tools": [t.get("name") for t in tools]})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


mcp_client = MCPClient()
