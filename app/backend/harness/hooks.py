"""
HookManager: lifecycle hooks for the agent execution pipeline.

Hooks fire at specific points in the AgentLoop:
- pre_tool_call: before a skill is executed (for logging, validation)
- post_tool_call: after a skill returns (for audit, side effects)
- pre_response: before sending the final response (for filtering)
- on_error: when an error occurs
"""
import logging
from typing import Callable, Awaitable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HookManager:
    def __init__(self):
        self._pre_tool: list[Callable] = []
        self._post_tool: list[Callable] = []
        self._pre_response: list[Callable] = []
        self._on_error: list[Callable] = []

    def register_pre_tool(self, fn: Callable):
        self._pre_tool.append(fn)

    def register_post_tool(self, fn: Callable):
        self._post_tool.append(fn)

    def register_pre_response(self, fn: Callable):
        self._pre_response.append(fn)

    def register_on_error(self, fn: Callable):
        self._on_error.append(fn)

    async def pre_tool_call(self, skill_name: str, params: dict):
        logger.debug(f"Hook: pre_tool_call({skill_name})")
        for fn in self._pre_tool:
            try:
                result = fn(skill_name, params)
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"pre_tool hook error: {e}")

    async def post_tool_call(self, skill_name: str, result_str: str):
        logger.debug(f"Hook: post_tool_call({skill_name}), result_len={len(result_str)}")
        for fn in self._post_tool:
            try:
                result = fn(skill_name, result_str)
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"post_tool hook error: {e}")

    async def pre_response(self, content: str) -> str:
        for fn in self._pre_response:
            try:
                result = fn(content)
                if hasattr(result, '__await__'):
                    content = await result
                elif isinstance(result, str):
                    content = result
            except Exception as e:
                logger.error(f"pre_response hook error: {e}")
        return content

    async def on_error(self, error: Exception):
        for fn in self._on_error:
            try:
                result = fn(error)
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"on_error hook error: {e}")


hook_manager = HookManager()


def _default_audit_hook(skill_name: str, result_str: str):
    """Built-in audit hook: logs tool calls to audit_logs table."""
    try:
        from database import SessionLocal
        from models import AuditLog
        db = SessionLocal()
        db.add(AuditLog(
            action=f"tool_call:{skill_name}",
            detail=result_str[:500],
            actor="agent",
            resource_type="skill",
            resource_id=skill_name,
            created_at=datetime.utcnow(),
        ))
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Audit hook DB error: {e}")


hook_manager.register_post_tool(_default_audit_hook)
