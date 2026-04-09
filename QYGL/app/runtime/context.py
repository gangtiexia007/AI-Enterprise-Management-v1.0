"""F07: Context Loader — 7-dimension context, 80 % threshold compression, verification.

Dimensions
----------
1. identity    — who is the AI agent (team config)
2. employee    — who we are talking to
3. history     — recent conversation turns
4. memories    — multi-layer memories (L1–L5)
5. knowledge   — company / department knowledge entries
6. team_status — operational counters (tasks, approvals, headcount)
7. goals       — active goals with progress

Compression is triggered when the token count exceeds 80 % of the model
context window.  The last 5 complete turns are preserved uncompressed.
A verification step ensures "current goal" and "unfinished steps" survive
the summarisation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_config
from app.core.database import Database

logger = logging.getLogger(__name__)


@dataclass
class ContextPayload:
    system_prompt: str = ""
    messages: list[dict] = field(default_factory=list)
    identity: dict = field(default_factory=dict)
    employee: dict | None = None
    memories: list[dict] = field(default_factory=list)
    knowledge: list[dict] = field(default_factory=list)
    team_status: dict = field(default_factory=dict)
    goals: list[dict] = field(default_factory=list)


class ContextManager:
    """Build, format, and compress the context window for each agent turn."""

    def __init__(
        self,
        db: Database | None = None,
        llm_client: Any | None = None,
    ):
        self.db = db or Database.get_instance()
        self._llm = llm_client

    @property
    def llm(self):
        if self._llm is None:
            from app.runtime.llm import LLMClient

            self._llm = LLMClient()
        return self._llm

    # ── Public: load all 7 dimensions ────────────────────────────

    async def load(
        self,
        team: dict[str, Any],
        employee: dict[str, Any] | None = None,
        conversation_id: str = "",
        current_plan_summary: str = "",
        extra_variables: dict[str, Any] | None = None,
    ) -> ContextPayload:
        team_id = team.get("id", "")
        employee_id = (employee or {}).get("id", "")

        identity = self._load_identity(team_id)
        raw_prompt = identity.get("system_prompt", "") or team.get("system_prompt", "")
        try:
            from app.runtime.prompt_engine import PromptEngine
            pe = PromptEngine()
            variables = pe.build_variables(
                team=team,
                employee=employee,
                team_status_summary="",
                current_plan_summary=current_plan_summary,
                extra=extra_variables,
            )
            system_prompt = pe.render(raw_prompt, variables)
        except Exception:
            system_prompt = raw_prompt

        context = {
            "identity": identity,
            "employee": self._load_employee(employee_id) if employee_id else (employee or {}),
            "history": self._load_history(team_id, employee_id, conversation_id),
            "memories": self._load_memories(team_id, employee_id),
            "knowledge": self._load_knowledge(team_id),
            "team_status": self._load_team_status(team_id),
            "goals": self._load_goals(team_id, employee_id),
        }

        if current_plan_summary:
            context["current_plan_summary"] = current_plan_summary
        if extra_variables:
            context["extra_variables"] = extra_variables

        messages = self.build_messages(context, system_prompt, current_message="")

        return ContextPayload(
            system_prompt=system_prompt,
            messages=messages,
            identity=identity,
            employee=employee,
            memories=context["memories"],
            knowledge=context["knowledge"],
            team_status=context["team_status"],
            goals=context["goals"],
        )

    # ── Public: assemble LLM message list ────────────────────────

    def build_messages(
        self,
        context: dict[str, Any],
        system_prompt: str,
        current_message: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        context_block = self._format_context_block(context)
        if context_block:
            messages.append({"role": "system", "content": context_block})

        for turn in context.get("history", []):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant", "tool") and content:
                messages.append({"role": role, "content": content})

        if current_message:
            messages.append({"role": "user", "content": current_message})

        return messages

    # ── Public: convert payload to LLM message list ────────────

    def to_messages(self, payload: ContextPayload) -> list[dict[str, Any]]:
        """Convert a ``ContextPayload`` into a flat message list for the LLM."""
        return list(payload.messages)

    # ── Public: compress if token budget is tight ────────────────

    async def compress_if_needed(
        self,
        messages: list[dict[str, Any]],
        model: str,
        context_window: int | None = None,
    ) -> list[dict[str, Any]]:
        """Compress older turns when tokens exceed the 80 % threshold.

        *context_window* defaults to the value reported by litellm for *model*.
        """
        cfg = get_config()
        threshold = cfg.context_compress_threshold
        keep_recent = cfg.context_keep_recent_turns

        if context_window is None:
            context_window = self.llm.get_context_window(model)

        current_tokens = self.llm.count_tokens(model, messages)
        token_limit = int(context_window * threshold)

        if current_tokens <= token_limit:
            return messages

        logger.info(
            "Compression triggered: %d tokens > %d limit (%.0f%% of %d)",
            current_tokens,
            token_limit,
            threshold * 100,
            context_window,
        )

        system_msgs = [m for m in messages if m.get("role") == "system"]
        conv_msgs = [m for m in messages if m.get("role") != "system"]

        recent: list[dict[str, Any]] = []
        older: list[dict[str, Any]] = []
        turn_count = 0
        for msg in reversed(conv_msgs):
            if msg["role"] == "user":
                turn_count += 1
            if turn_count <= keep_recent:
                recent.insert(0, msg)
            else:
                older.append(msg)
        older.reverse()

        if not older:
            return messages

        from app.runtime.model_router import ModelRouter

        router = ModelRouter.get_instance(self.db)
        cheap = router.select_cheap_model()
        cheap_key = router.decrypt_api_key_for_model(cheap)
        llm_kw: dict[str, Any] = {}
        if cheap_key:
            llm_kw["api_key"] = cheap_key

        summary_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}" for m in older if m.get("content")
        )

        compress_prompt = [
            {
                "role": "system",
                "content": (
                    "你是对话压缩助手。将以下对话历史压缩为简洁的结构化摘要，\n"
                    "必须保留：\n"
                    "1. 当前目标（current goal）\n"
                    "2. 未完成的步骤（unfinished steps）\n"
                    "3. 重要决策和结论\n"
                    "4. 待处理问题\n"
                    "输出中文。"
                ),
            },
            {"role": "user", "content": summary_text},
        ]

        resp = await self.llm.complete(cheap, compress_prompt, temperature=0.3, **llm_kw)
        compressed = resp.content

        if not self._verify_compression(compressed):
            logger.warning("Compression verification failed — retrying with stricter prompt")
            compress_prompt[0]["content"] += (
                '\n\n重要：请确保摘要中明确包含「当前目标」和「未完成步骤」两个小节。'
            )
            resp = await self.llm.complete(cheap, compress_prompt, temperature=0.2, **llm_kw)
            compressed = resp.content

        result = (
            system_msgs
            + [{"role": "system", "content": f"[对话历史摘要]\n{compressed}"}]
            + recent
        )

        new_tokens = self.llm.count_tokens(model, result)
        logger.info(
            "Compressed: %d → %d tokens (%.0f%% reduction)",
            current_tokens,
            new_tokens,
            (1 - new_tokens / max(current_tokens, 1)) * 100,
        )
        return result

    # ── Dimension loaders (private) ──────────────────────────────

    def _load_identity(self, team_id: str) -> dict[str, Any]:
        team = self.db.get_by_id("teams", team_id)
        if not team:
            return {}
        return {
            "team_id": team_id,
            "team_name": team.get("display_name") or team.get("name", ""),
            "department": team.get("department", ""),
            "system_prompt": team.get("system_prompt", ""),
            "automation_profile": team.get("automation_profile", ""),
        }

    def _load_employee(self, employee_id: str) -> dict[str, Any]:
        emp = self.db.get_by_id("employees", employee_id)
        if not emp:
            return {}
        return {
            "id": emp["id"],
            "name": emp.get("name", ""),
            "role": emp.get("role", ""),
            "department": emp.get("department", ""),
            "status": emp.get("status", ""),
            "join_date": emp.get("join_date", ""),
            "notes": emp.get("notes", ""),
        }

    def _load_history(
        self, team_id: str, employee_id: str, conversation_id: str
    ) -> list[dict[str, Any]]:
        if conversation_id:
            conv = self.db.get_by_id("conversations", conversation_id)
            if conv:
                turns = self._parse_turns(conv.get("turns_json", "[]"))
                summary = (conv.get("summary") or "").strip()
                if summary:
                    turns = [{"role": "system", "content": f"[对话历史摘要]\n{summary}"}] + turns
                return turns

        conditions: dict[str, Any] = {"team_id": team_id}
        if employee_id:
            conditions["employee_id"] = employee_id
        rows = self.db.query("conversations", conditions, order_by="updated_at DESC", limit=1)
        if not rows:
            return []
        conv = rows[0]
        turns = self._parse_turns(conv.get("turns_json", "[]"))
        summary = (conv.get("summary") or "").strip()
        if summary:
            turns = [{"role": "system", "content": f"[对话历史摘要]\n{summary}"}] + turns
        return turns

    def _load_memories(self, team_id: str, employee_id: str) -> list[dict[str, Any]]:
        team_mems = self.db.query(
            "memories",
            {"team_id": team_id},
            order_by="layer ASC, created_at DESC",
            limit=20,
        )
        seen = {m["id"] for m in team_mems}

        if employee_id:
            emp_mems = self.db.query(
                "memories",
                {"employee_id": employee_id},
                order_by="layer ASC, created_at DESC",
                limit=10,
            )
            for m in emp_mems:
                if m["id"] not in seen:
                    team_mems.append(m)
                    seen.add(m["id"])

        return [
            {
                "layer": m.get("layer", ""),
                "content": m.get("content", ""),
                "source": m.get("source", ""),
                "created_at": str(m.get("created_at", "")),
            }
            for m in team_mems
        ]

    def _load_knowledge(self, team_id: str) -> list[dict[str, Any]]:
        team = self.db.get_by_id("teams", team_id)
        department = team.get("department", "") if team else ""

        company = self.db.query(
            "knowledge",
            {"scope": "company", "status": "active"},
            order_by="created_at DESC",
            limit=10,
        )

        dept: list[dict[str, Any]] = []
        if department:
            dept = self.db.query(
                "knowledge",
                {"scope": "department", "department": department, "status": "active"},
                order_by="created_at DESC",
                limit=10,
            )

        return [
            {
                "title": k.get("title", ""),
                "content": k.get("content", ""),
                "category": k.get("category", ""),
            }
            for k in company + dept
        ]

    def _load_team_status(self, team_id: str) -> dict[str, Any]:
        return {
            "employee_count": self.db.count("employees", {"team_id": team_id, "status": "active"}),
            "active_tasks": self.db.count("tasks", {"team_id": team_id, "status": "in_progress"}),
            "pending_tasks": self.db.count("tasks", {"team_id": team_id, "status": "pending"}),
            "overdue_tasks": self.db.count("tasks", {"team_id": team_id, "status": "overdue"}),
            "pending_approvals": self.db.count(
                "approval_requests", {"team_id": team_id, "status": "pending"}
            ),
        }

    def _load_goals(self, team_id: str, employee_id: str) -> list[dict[str, Any]]:
        team_goals = self.db.query(
            "goals",
            {"team_id": team_id, "status": "active"},
            order_by="created_at DESC",
            limit=10,
        )
        seen = {g["id"] for g in team_goals}

        if employee_id:
            personal = self.db.query(
                "goals",
                {"employee_id": employee_id, "status": "active"},
                order_by="created_at DESC",
                limit=5,
            )
            for g in personal:
                if g["id"] not in seen:
                    team_goals.append(g)
                    seen.add(g["id"])

        return [
            {
                "title": g.get("title", ""),
                "level": g.get("level", ""),
                "target_value": g.get("target_value", 0),
                "current_value": g.get("current_value", 0),
                "unit": g.get("unit", ""),
                "status": g.get("status", ""),
            }
            for g in team_goals
        ]

    # ── Formatting helpers ───────────────────────────────────────

    def _format_context_block(self, context: dict[str, Any]) -> str:
        parts: list[str] = []

        emp = context.get("employee", {})
        if emp and emp.get("name"):
            parts.append(
                f"[当前对话员工] {emp['name']} | 角色: {emp.get('role', '')} | "
                f"部门: {emp.get('department', '')} | 状态: {emp.get('status', '')}"
            )

        status = context.get("team_status", {})
        if status:
            parts.append(
                f"[团队状态] 在岗: {status.get('employee_count', 0)} | "
                f"进行中: {status.get('active_tasks', 0)} | "
                f"待处理: {status.get('pending_tasks', 0)} | "
                f"逾期: {status.get('overdue_tasks', 0)} | "
                f"待审批: {status.get('pending_approvals', 0)}"
            )

        goals = context.get("goals", [])
        if goals:
            lines = []
            for g in goals[:5]:
                progress = ""
                target = g.get("target_value", 0)
                if target:
                    pct = (g.get("current_value", 0) / target) * 100
                    progress = f" ({pct:.0f}%)"
                lines.append(f"  - {g.get('title', '')}{progress}")
            parts.append("[当前目标]\n" + "\n".join(lines))

        memories = context.get("memories", [])
        if memories:
            lines = [f"  [{m.get('layer', '')}] {m.get('content', '')}" for m in memories[:10]]
            parts.append("[记忆]\n" + "\n".join(lines))

        knowledge = context.get("knowledge", [])
        if knowledge:
            lines = [
                f"  - {k.get('title', '')}: {k.get('content', '')[:200]}"
                for k in knowledge[:5]
            ]
            parts.append("[知识库]\n" + "\n".join(lines))

        return "\n\n".join(parts)

    @staticmethod
    def _parse_turns(raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @staticmethod
    def _verify_compression(summary: str) -> bool:
        lower = summary.lower()
        has_goal = any(kw in lower for kw in ("目标", "goal", "计划", "plan", "任务"))
        has_steps = any(
            kw in lower
            for kw in ("步骤", "step", "待完成", "未完成", "进行中", "下一步")
        )
        return has_goal and has_steps
