"""F32: Memory Distiller — compress daily conversations into summaries.

Runs nightly (scheduled at 2:00 AM) to:
1. Gather all conversations for a team on a given date
2. Compress them into structured summaries
3. Save summaries as L5 memory entries
4. Delete original conversations older than 7 days
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.database import new_id
from app.core.enums import MemoryLayer
from app.engines.base import EngineBase

logger = logging.getLogger(__name__)

RETENTION_DAYS = 7


class MemoryDistiller(EngineBase):
    """Compresses daily conversations into memory summaries."""

    def distill_conversations(
        self,
        team_id: str,
        date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Distill all conversations for *team_id* on *date* into summaries.

        Args:
            team_id: The team to distill.
            date: ISO date string (YYYY-MM-DD). Defaults to yesterday.

        Returns:
            List of created memory summaries.
        """
        if date is None:
            date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

        conversations = self._fetch_conversations(team_id, date)
        if not conversations:
            logger.info("No conversations to distill for team=%s date=%s", team_id, date)
            return []

        groups = self._group_by_employee(conversations)
        summaries: list[dict[str, Any]] = []

        for employee_id, convs in groups.items():
            summary_text = self._compress(convs, employee_id)
            memory = {
                "id": new_id(),
                "layer": MemoryLayer.L5.value,
                "team_id": team_id,
                "employee_id": employee_id,
                "content": summary_text,
                "metadata_json": {
                    "date": date,
                    "conversation_count": len(convs),
                    "source": "distiller",
                },
                "source": "dream_distiller",
                "created_by": "system",
                "created_at": self._now_iso(),
            }
            self._insert("memories", memory)
            summaries.append(memory)

        self._cleanup_old_conversations(team_id)

        logger.info(
            "Distilled %d conversations → %d summaries for team %s on %s",
            len(conversations), len(summaries), team_id, date,
        )
        return summaries

    def _fetch_conversations(self, team_id: str, date: str) -> list[dict[str, Any]]:
        date_start = f"{date}T00:00:00"
        date_end = f"{date}T23:59:59"
        return self._execute(
            "SELECT * FROM conversations WHERE team_id=? "
            "AND created_at >= ? AND created_at <= ? "
            "ORDER BY created_at ASC",
            (team_id, date_start, date_end),
        )

    def _group_by_employee(
        self, conversations: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for conv in conversations:
            eid = conv.get("employee_id", "unknown")
            groups.setdefault(eid, []).append(conv)
        return groups

    def _compress(
        self,
        conversations: list[dict[str, Any]],
        employee_id: str,
    ) -> str:
        """Distill conversations into L5 memory text using LLM when possible."""
        employee_name = self._employee_display_name(employee_id)
        turns = self._flatten_turns(conversations)
        if turns:
            turns_text = "\n".join(
                [
                    f"{'用户' if t.get('role') == 'user' else 'AI'}: "
                    f"{str(t.get('content', ''))[:500]}"
                    for t in turns[-20:]
                ]
            )
        else:
            summaries = [
                c.get("summary", "").strip()
                for c in sorted(
                    conversations, key=lambda x: x.get("created_at", "")
                )
                if c.get("summary", "").strip()
            ]
            turns_text = "\n".join(summaries)[:2000]

        if not turns_text.strip():
            return "无实质性对话内容。"

        prompt = f"""请将以下对话总结为3-5条关键信息点，用于AI记忆存储。
要求：
1. 只保留有业务价值的信息（决策、偏好、指标、反馈）
2. 去掉寒暄和重复内容
3. 每条信息独立成句

员工: {employee_name}
对话内容:
{turns_text}

请输出摘要:"""

        distilled = self._distill_with_llm(prompt)
        if distilled:
            return distilled

        return turns_text[:500] if turns_text else "无实质性对话内容。"

    def _employee_display_name(self, employee_id: str) -> str:
        if not employee_id or employee_id == "unknown":
            return ""
        row = self._get_by_id_optional("employees", employee_id)
        return (row or {}).get("name", "") or ""

    def _flatten_turns(
        self, conversations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        ordered = sorted(conversations, key=lambda c: c.get("created_at", ""))
        out: list[dict[str, Any]] = []
        for conv in ordered:
            raw = conv.get("turns_json", "[]")
            parsed = self._parse_json_field(raw)
            if isinstance(parsed, list):
                out.extend([t for t in parsed if isinstance(t, dict)])
        return out

    def _distill_with_llm(self, prompt: str) -> str:
        try:
            from app.runtime.llm import LLMClient
            from app.runtime.model_router import ModelRouter

            router = ModelRouter.get_instance()
            model_name = router.select_cheap_model()
            api_key = router.decrypt_api_key_for_model(model_name) or ""
            kwargs: dict[str, Any] = {}
            if api_key:
                kwargs["api_key"] = api_key

            async def _call() -> str:
                client = LLMClient()
                resp = await client.complete(
                    model_name,
                    [{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500,
                    **kwargs,
                )
                return (resp.content or "").strip()

            try:
                out = asyncio.run(_call())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    out = loop.run_until_complete(_call())
                finally:
                    loop.close()
            return out
        except Exception as exc:
            logger.warning(
                "LLM distillation failed, falling back to truncation: %s", exc
            )
            return ""

    def _cleanup_old_conversations(self, team_id: str) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        old_convs = self._execute(
            "SELECT id FROM conversations WHERE team_id=? AND created_at < ?",
            (team_id, cutoff),
        )
        count = 0
        for conv in old_convs:
            self._delete("conversations", conv["id"])
            count += 1

        if count:
            logger.info("Deleted %d old conversations for team %s", count, team_id)
        return count
