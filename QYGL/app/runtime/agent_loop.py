"""F06: Agent Loop — 9-state machine driving every AI employee interaction.

State transitions::

    IDLE → RECEIVING_INPUT → (is command?) ─yes─→ COMMAND_ROUTING ─┐
                             └─no──→ LOADING_CONTEXT → THINKING    │
                                         ↑                        │
                                         │        ┌───────────────┘
                                         │        ↓
                             CALLING_TOOL ← (tool call?)
                                  │
                                  ↓
                             OBSERVING_RESULT → (more turns?) → THINKING
                                                  └──no──→ RESPONDING → IDLE
                             ERROR_HANDLING → RESPONDING → IDLE

Hard constraints:
- Max 15 turns per invocation (configurable per team).
- Messages starting with ``/`` bypass the LLM and route to the skill registry.
- ``{current_plan_summary}`` is updated after each tool result.
- Processing is serial per employee (one message at a time).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_config
from app.core.database import Database, new_id
from app.core.enums import AgentLoopState, PermissionLevel
from app.core.events import Events
from app.core.exceptions import AgentLoopMaxTurns, QFBJError, ToolCallFailed
from app.core.models import AgentResponse, UnifiedMessage
from app.runtime.context import ContextManager, ContextPayload
from app.runtime.llm import LLMClient, LLMResponse
from app.runtime.model_router import ModelRouter
from app.skills.sdk import ToolCall, ToolContext, ToolResult, execute_tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 15

_ROLE_TO_TIER = {"boss": "T1", "manager": "T2", "employee": "T3"}

_employee_locks: dict[str, asyncio.Lock] = {}


def _get_employee_lock(employee_id: str) -> asyncio.Lock:
    if employee_id not in _employee_locks:
        _employee_locks[employee_id] = asyncio.Lock()
    return _employee_locks[employee_id]


@dataclass
class LoopSession:
    """Mutable state for one invocation of the agent loop."""

    team_id: str
    employee_id: str
    conversation_id: str
    state: AgentLoopState = AgentLoopState.IDLE
    turn: int = 0
    max_turns: int = DEFAULT_MAX_TURNS
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    current_plan_summary: str = ""
    model: str = ""
    tool_context: ToolContext = field(default_factory=ToolContext)
    errors: list[str] = field(default_factory=list)
    llm_api_key: str | None = None


class AgentLoop:
    """Core agent loop implementing the 9-state machine.

    Each public call to ``run`` processes exactly one user message and
    returns an ``AgentResponse``.  Processing is serialized per employee.
    """

    def __init__(
        self,
        db: Database | None = None,
        llm: LLMClient | None = None,
        context_mgr: ContextManager | None = None,
        model_router: ModelRouter | None = None,
    ):
        self._db = db or Database.get_instance()
        self._llm = llm or LLMClient()
        self._ctx = context_mgr or ContextManager(self._db, self._llm)
        self._router = model_router or ModelRouter.get_instance(self._db)

    # ── Public API ───────────────────────────────────────────────

    async def run(
        self,
        message: UnifiedMessage,
        *,
        team: dict[str, Any],
        employee: dict[str, Any] | None = None,
        conversation_id: str = "",
        extra_variables: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Process a single user message through the 9-state machine.

        Acquires a per-employee lock to ensure serial processing.
        """
        employee_id = (employee or {}).get("id", "") or message.employee_id
        lock = _get_employee_lock(employee_id)

        async with lock:
            return await self._run_locked(
                message, team=team, employee=employee,
                conversation_id=conversation_id,
                extra_variables=extra_variables,
            )

    async def _run_locked(
        self,
        message: UnifiedMessage,
        *,
        team: dict[str, Any],
        employee: dict[str, Any] | None,
        conversation_id: str,
        extra_variables: dict[str, Any] | None,
    ) -> AgentResponse:
        team_id = team["id"]
        employee_id = (employee or {}).get("id", "") or message.employee_id

        session = LoopSession(
            team_id=team_id,
            employee_id=employee_id,
            conversation_id=conversation_id or self._ensure_conversation(team_id, employee_id),
            max_turns=self._resolve_max_turns(team),
        )

        session.tool_context = ToolContext(
            team_id=team_id,
            employee_id=employee_id,
            user_tier=_ROLE_TO_TIER.get((employee or {}).get("role", "employee"), "T3"),
            caller_permission=self._resolve_permission(employee),
            actor=employee_id,
            department=(employee or {}).get("department", ""),
            conversation_id=session.conversation_id,
        )

        self._transition(session, AgentLoopState.RECEIVING_INPUT)

        content = message.content.strip()
        has_file = bool(message.file_path)

        if content.startswith("/") and not has_file:
            return await self._handle_command(session, content)

        if has_file and not content:
            file_context = self._parse_uploaded_file(message.file_path, message.file_name)
            if file_context:
                content = file_context
            else:
                content = f"[用户发送了文件: {message.file_name or '未知文件'}，但解析失败]"
        elif has_file and content:
            file_context = self._parse_uploaded_file(message.file_path, message.file_name)
            if file_context:
                content = f"{content}\n\n{file_context}"

        self._transition(session, AgentLoopState.LOADING_CONTEXT)

        payload = await self._ctx.load(
            team=team,
            employee=employee,
            conversation_id=session.conversation_id,
            current_plan_summary=session.current_plan_summary,
            extra_variables=extra_variables,
        )

        session.messages = self._ctx.to_messages(payload)
        session.messages.append({"role": "user", "content": content})

        model_bundle = self._router.get_model_with_key(team_id)
        session.model = model_bundle["model"]
        session.llm_api_key = model_bundle.get("api_key")

        session.tool_schemas = self._load_tool_schemas(team_id)

        return await self._think_loop(session)

    # ── State: COMMAND_ROUTING ───────────────────────────────────

    async def _handle_command(
        self, session: LoopSession, content: str,
    ) -> AgentResponse:
        """Messages starting with ``/`` bypass the LLM entirely."""
        self._transition(session, AgentLoopState.COMMAND_ROUTING)

        parts = content.split(maxsplit=1)
        command = parts[0].lstrip("/")
        args_str = parts[1] if len(parts) > 1 else ""

        try:
            args = json.loads(args_str) if args_str.startswith("{") else {}
        except (json.JSONDecodeError, TypeError):
            args = {}

        if not args and args_str:
            args = {"query": args_str}

        call = ToolCall(tool_name=command, arguments=args)
        result = await execute_tool(call, session.tool_context)

        self._transition(session, AgentLoopState.RESPONDING)
        self._save_turn(session, content, result_to_str(result))

        return AgentResponse(
            content=result_to_str(result),
            metadata={
                "command": command,
                "success": result.success,
                "elapsed_ms": result.elapsed_ms,
            },
        )

    # ── State: THINKING ↔ CALLING_TOOL ↔ OBSERVING_RESULT ──────

    async def _think_loop(self, session: LoopSession) -> AgentResponse:
        """LLM think → tool call → observe loop with turn budget."""
        while session.turn < session.max_turns:
            session.turn += 1
            self._transition(session, AgentLoopState.THINKING)

            if session.turn > 1:
                try:
                    session.messages = await self._ctx.compress_if_needed(
                        session.messages, session.model,
                    )
                except Exception:
                    logger.debug("Context compression skipped", exc_info=True)

            try:
                llm_kw: dict[str, Any] = {}
                if session.llm_api_key:
                    llm_kw["api_key"] = session.llm_api_key
                llm_resp = await self._llm.complete(
                    model=session.model,
                    messages=session.messages,
                    tools=session.tool_schemas or None,
                    temperature=0.7,
                    **llm_kw,
                )
            except QFBJError as exc:
                return self._handle_error(session, str(exc))
            except Exception as exc:
                return self._handle_error(session, f"LLM error: {exc}")

            self._router.record_usage(
                session.model, session.team_id,
                llm_resp.prompt_tokens, llm_resp.completion_tokens,
            )

            if not llm_resp.has_tool_calls:
                self._transition(session, AgentLoopState.RESPONDING)
                self._save_turn(session, None, llm_resp.content)
                return AgentResponse(
                    content=llm_resp.content,
                    metadata={"turns": session.turn, "model": session.model},
                )

            self._transition(session, AgentLoopState.CALLING_TOOL)
            session.messages.append(self._assistant_msg(llm_resp))

            tool_results = await self._execute_tool_calls(session, llm_resp.tool_calls)

            self._transition(session, AgentLoopState.OBSERVING_RESULT)

            for tc, result in tool_results:
                session.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_to_str(result),
                })

            session.current_plan_summary = self._update_plan_summary(
                session.current_plan_summary, tool_results,
            )

        return self._handle_max_turns(session)

    async def _execute_tool_calls(
        self,
        session: LoopSession,
        tool_calls: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], ToolResult]]:
        """Execute all tool calls from a single LLM response (sequential)."""
        results: list[tuple[dict[str, Any], ToolResult]] = []

        for tc in tool_calls:
            func_info = tc.get("function", {})
            tool_name = func_info.get("name", "")
            raw_args = func_info.get("arguments", "{}")

            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except (json.JSONDecodeError, TypeError):
                args = {}

            call = ToolCall(tool_name=tool_name, arguments=args, call_id=tc.get("id", ""))

            if tool_name == "invoke_sub_agent":
                result = await self._invoke_sub_agent(session, args)
                results.append((tc, result))
                continue

            result = await execute_tool(call, session.tool_context)
            results.append((tc, result))

            if not result.success:
                logger.warning(
                    "Tool %s failed: %s (team=%s, turn=%d)",
                    tool_name, result.error, session.team_id, session.turn,
                )

        return results

    async def _invoke_sub_agent(self, session: LoopSession, args: dict) -> ToolResult:
        try:
            from app.runtime.sub_agent import SubAgentRunner
            runner = SubAgentRunner(db=self._db, llm=self._llm, model_router=self._router)
            team = self._db.get_by_id("teams", session.team_id)
            if not team:
                return ToolResult(call_id="", tool_name="invoke_sub_agent", success=False, error="Team not found")
            employee = self._db.get_by_id("employees", session.employee_id) if session.employee_id else None
            resp = await runner.invoke(
                team=team,
                sub_agent_name=args.get("sub_agent_name", ""),
                user_content=args.get("task_description", ""),
                parent_permission=session.tool_context.caller_permission,
                employee=employee,
                conversation_id=session.conversation_id,
            )
            return ToolResult(call_id="", tool_name="invoke_sub_agent", success=True, data={"response": resp.content, "sub_agent": resp.metadata.get("sub_agent", "")})
        except Exception as e:
            return ToolResult(call_id="", tool_name="invoke_sub_agent", success=False, error=str(e))

    # ── State: ERROR_HANDLING ────────────────────────────────────

    def _handle_error(self, session: LoopSession, error_msg: str) -> AgentResponse:
        self._transition(session, AgentLoopState.ERROR_HANDLING)
        session.errors.append(error_msg)
        logger.error(
            "AgentLoop error (team=%s, turn=%d): %s",
            session.team_id, session.turn, error_msg,
        )
        self._transition(session, AgentLoopState.RESPONDING)
        user_msg = "抱歉，处理您的请求时遇到了问题，请稍后重试。"
        self._save_turn(session, None, user_msg)
        return AgentResponse(
            content=user_msg,
            metadata={
                "error": error_msg,
                "turns": session.turn,
                "model": session.model,
            },
        )

    def _handle_max_turns(self, session: LoopSession) -> AgentResponse:
        self._transition(session, AgentLoopState.ERROR_HANDLING)
        logger.warning(
            "Max turns (%d) reached for team %s",
            session.max_turns, session.team_id,
        )
        last_content = ""
        for msg in reversed(session.messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                last_content = msg["content"]
                break

        self._transition(session, AgentLoopState.RESPONDING)
        user_msg = last_content or "已达到最大处理轮次，当前结果如上。如需继续，请发送新消息。"
        self._save_turn(session, None, user_msg)
        return AgentResponse(
            content=user_msg,
            metadata={
                "max_turns_reached": True,
                "turns": session.max_turns,
                "plan_summary": session.current_plan_summary,
            },
        )

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _transition(session: LoopSession, new_state: AgentLoopState) -> None:
        logger.debug(
            "Loop state: %s → %s (team=%s, turn=%d)",
            session.state.value, new_state.value, session.team_id, session.turn,
        )
        session.state = new_state

    @staticmethod
    def _assistant_msg(llm_resp: LLMResponse) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": llm_resp.content or ""}
        if llm_resp.tool_calls:
            msg["tool_calls"] = llm_resp.tool_calls
        return msg

    @staticmethod
    def _update_plan_summary(
        current: str,
        tool_results: list[tuple[dict[str, Any], ToolResult]],
    ) -> str:
        """Append a one-line summary of each completed tool call."""
        lines = [current] if current else []
        for tc, result in tool_results:
            name = tc.get("function", {}).get("name", "unknown")
            status = "✓" if result.success else "✗"
            snippet = (result.error or str(result.data) or "")[:80]
            lines.append(f"[{status}] {name}: {snippet}")
        return "\n".join(lines[-20:])

    def _load_tool_schemas(self, team_id: str) -> list[dict[str, Any]]:
        try:
            from app.skills.registry import SkillRegistry
            registry = SkillRegistry.get_instance(self._db)
            schemas = registry.get_tool_schemas_for_team(team_id)
        except Exception:
            logger.debug("Could not load tool schemas for team %s", team_id, exc_info=True)
            schemas = []

        sub_agents = self._db.query("sub_agents", {"team_id": team_id}, limit=20)
        if sub_agents:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "invoke_sub_agent",
                    "description": "调用子Agent完成专项任务。可用子Agent: " + ", ".join(
                        f"{sa.get('name','')}({sa.get('role','')})" for sa in sub_agents
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sub_agent_name": {"type": "string", "description": "子Agent名称"},
                            "task_description": {"type": "string", "description": "要交给子Agent的任务描述"},
                        },
                        "required": ["sub_agent_name", "task_description"],
                    },
                },
            })
        return schemas

    def _resolve_max_turns(self, team: dict[str, Any]) -> int:
        cfg = get_config()
        team_max = 0
        esc = team.get("escalation_json", {})
        if isinstance(esc, dict):
            team_max = esc.get("max_agent_turns", 0)
        return team_max or cfg.max_agent_turns or DEFAULT_MAX_TURNS

    @staticmethod
    def _resolve_permission(employee: dict[str, Any] | None) -> int:
        if not employee:
            return PermissionLevel.P0
        role = employee.get("role", "employee")
        mapping = {"boss": PermissionLevel.P4, "manager": PermissionLevel.P3, "employee": PermissionLevel.P1}
        base = mapping.get(role, PermissionLevel.P0)
        sub_cap = employee.get("_sub_agent_permission")
        if sub_cap is not None:
            return min(base, sub_cap)
        return base

    def _parse_uploaded_file(self, file_path: str, file_name: str = "") -> str:
        """Parse an uploaded file and return structured text for the LLM context."""
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            logger.warning("File not found: %s", file_path)
            return ""

        ext = path.suffix.lower()
        name = file_name or path.name

        try:
            if ext in (".xlsx", ".xls"):
                try:
                    import openpyxl
                except ImportError:
                    return f"[文件 {name}: 缺少 openpyxl 依赖，无法解析 Excel]"
                wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
                ws = wb.active
                if ws is None:
                    wb.close()
                    return f"[文件 {name}: Excel 无活动工作表]"
                all_rows = list(ws.iter_rows(values_only=True))
                wb.close()
                if not all_rows:
                    return f"[文件 {name}: Excel 为空]"
                cols = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(all_rows[0])]
                data_rows = all_rows[1:21]
                header = " | ".join(cols)
                lines = [f"[文件: {name}，共 {len(all_rows) - 1} 行]", header, "-" * len(header)]
                for row in data_rows:
                    lines.append(" | ".join(str(v) if v is not None else "" for v in row))
                if len(all_rows) > 21:
                    lines.append(f"... 还有 {len(all_rows) - 21} 行未显示")
                return "\n".join(lines)

            elif ext == ".csv":
                import csv
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    all_rows = list(reader)
                if not all_rows:
                    return f"[文件 {name}: CSV 为空]"
                cols = all_rows[0]
                data_rows = all_rows[1:21]
                header = " | ".join(cols)
                lines = [f"[文件: {name}，共 {len(all_rows) - 1} 行数据]", header, "-" * len(header)]
                for row in data_rows:
                    lines.append(" | ".join(row))
                if len(all_rows) > 21:
                    lines.append(f"... 还有 {len(all_rows) - 21} 行未显示")
                return "\n".join(lines)

            elif ext in (".txt", ".md"):
                text = path.read_text(encoding="utf-8", errors="replace")[:5000]
                return f"[文件: {name}]\n{text}"

            elif ext == ".json":
                import json as _json
                data = _json.loads(path.read_text(encoding="utf-8", errors="replace"))
                preview = _json.dumps(data, ensure_ascii=False, indent=2)[:3000]
                return f"[文件: {name}]\n{preview}"

            else:
                return f"[文件: {name}，格式 {ext} 暂不支持自动解析]"

        except Exception as exc:
            logger.warning("File parse error for %s: %s", file_path, exc)
            return f"[文件 {name} 解析异常: {exc}]"

    def _ensure_conversation(self, team_id: str, employee_id: str) -> str:
        """Find or create a conversation record."""
        rows = self._db.query(
            "conversations",
            {"team_id": team_id, "employee_id": employee_id},
            order_by="updated_at DESC",
            limit=1,
        )
        if rows:
            return rows[0]["id"]
        cid = new_id()
        self._db.insert("conversations", {
            "id": cid,
            "team_id": team_id,
            "employee_id": employee_id,
            "channel": "dashboard",
            "turns_json": [],
            "summary": "",
        })
        return cid

    def _save_turn(
        self,
        session: LoopSession,
        user_content: str | None,
        assistant_content: str,
    ) -> None:
        """Append a turn to the conversation record."""
        try:
            row = self._db.get_by_id("conversations", session.conversation_id)
            if not row:
                return
            turns_raw = row.get("turns_json", "[]")
            if isinstance(turns_raw, str):
                try:
                    turns = json.loads(turns_raw)
                except (json.JSONDecodeError, TypeError):
                    turns = []
            else:
                turns = turns_raw

            if user_content:
                turns.append({"role": "user", "content": user_content})
            if assistant_content:
                turns.append({"role": "assistant", "content": assistant_content})

            self._db.update("conversations", session.conversation_id, {
                "turns_json": turns,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            if len(turns) > 20:
                try:
                    summary_turns = turns[:-10]
                    recent_turns = turns[-10:]
                    summary_text = "\n".join(
                        f"[{t.get('role','')}]: {t.get('content','')[:200]}"
                        for t in summary_turns if t.get('content')
                    )
                    self._db.update("conversations", session.conversation_id, {
                        "turns_json": recent_turns,
                        "summary": (row.get("summary", "") + "\n---\n" + summary_text)[-3000:],
                    })
                except Exception:
                    pass
        except Exception:
            logger.debug("Failed to save turn", exc_info=True)


def result_to_str(result: ToolResult) -> str:
    """Convert a ``ToolResult`` to a string suitable for the LLM messages."""
    if result.success:
        if isinstance(result.data, (dict, list)):
            return json.dumps(result.data, ensure_ascii=False, default=str)
        return str(result.data) if result.data is not None else "(done)"
    return f"Error: {result.error}"
