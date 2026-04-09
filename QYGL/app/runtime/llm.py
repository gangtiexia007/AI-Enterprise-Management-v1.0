"""F08: Unified LLM call interface — streaming, non-streaming, token counting, retries.

All LLM interactions in the system go through LLMClient.  It wraps litellm
so the rest of the codebase stays decoupled from any specific provider SDK.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import litellm
from litellm import acompletion, token_counter

from app.core.exceptions import QFBJError

logger = logging.getLogger(__name__)

litellm.drop_params = True
litellm.set_verbose = False


# ── Response wrapper ─────────────────────────────────────────────────


@dataclass
class LLMResponse:
    """Normalised response from any LLM provider."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    finish_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# ── Client ───────────────────────────────────────────────────────────


class LLMClient:
    """Unified LLM call interface with automatic retries and token counting."""

    def __init__(self, max_retries: int = 3, retry_base_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    # ── Non-streaming completion ─────────────────────────────────

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                params = self._build_params(
                    model, messages, tools, temperature, max_tokens, **kwargs,
                )
                resp = await acompletion(**params)
                return self._parse(resp, model)
            except Exception as exc:
                last_err = exc
                logger.warning(
                    "LLM attempt %d/%d failed (%s): %s",
                    attempt,
                    self.max_retries,
                    model,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_base_delay * attempt)

        raise QFBJError(
            f"All {self.max_retries} attempts failed for '{model}': {last_err}",
            code="LLM_CALL_ERROR",
        )

    # ── Streaming completion ─────────────────────────────────────

    async def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        params = self._build_params(
            model, messages, tools, temperature, max_tokens, stream=True, **kwargs,
        )
        try:
            resp = await acompletion(**params)
            async for chunk in resp:
                choice = chunk.choices[0] if chunk.choices else None
                if choice and choice.delta and choice.delta.content:
                    yield choice.delta.content
        except Exception as exc:
            raise QFBJError(
                f"Streaming failed for '{model}': {exc}",
                code="LLM_STREAM_ERROR",
            ) from exc

    # ── Token counting ───────────────────────────────────────────

    def count_tokens(self, model: str, messages: list[dict[str, Any]]) -> int:
        try:
            return token_counter(model=model, messages=messages)
        except Exception:
            total_chars = sum(len(str(m.get("content", ""))) for m in messages)
            return total_chars // 4

    def count_text_tokens(self, model: str, text: str) -> int:
        return self.count_tokens(model, [{"role": "user", "content": text}])

    def get_context_window(self, model: str) -> int:
        """Return the context window size for *model*, defaulting to 128 000."""
        try:
            info = litellm.get_model_info(model=model)
            return info.get("max_input_tokens") or info.get("max_tokens") or 128_000
        except Exception:
            return 128_000

    # ── Internals ────────────────────────────────────────────────

    @staticmethod
    def _to_litellm_model(model: str) -> str:
        """Map DB model names to litellm provider ids (e.g. deepseek-chat → deepseek/deepseek-chat)."""
        m = (model or "").strip()
        if not m or m.startswith("deepseek/"):
            return m
        low = m.lower()
        if low.startswith("deepseek-"):
            return f"deepseek/{m}"
        return m

    @staticmethod
    def _build_params(
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int | None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        litellm_model = LLMClient._to_litellm_model(model)
        params: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            params["tools"] = tools
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if stream:
            params["stream"] = True
        params.update(kwargs)
        return params

    @staticmethod
    def _parse(response: Any, model: str) -> LLMResponse:
        choice = response.choices[0]
        msg = choice.message

        tool_calls: list[dict[str, Any]] = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        usage = response.usage
        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            model=model,
            finish_reason=choice.finish_reason or "",
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
        )
