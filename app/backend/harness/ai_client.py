"""OpenAI-compatible API client with automatic fallback."""
import logging
from typing import Optional, AsyncGenerator
import httpx
from database import SessionLocal
from models import Setting, TokenUsage
from datetime import datetime

logger = logging.getLogger(__name__)

def _get_setting(key: str, default: str = "") -> str:
    db = SessionLocal()
    try:
        s = db.query(Setting).filter(Setting.key == key).first()
        return s.value if s else default
    finally:
        db.close()

class AIClient:
    def _get_config(self):
        return {
            "base_url": _get_setting("ai_base_url", "https://api.openai.com/v1"),
            "api_key": _get_setting("ai_api_key", ""),
            "model_primary": _get_setting("ai_model_primary", "gpt-4o-mini"),
            "model_fallback": _get_setting("ai_model_fallback", "gpt-3.5-turbo"),
        }

    def _record_usage(self, model: str, prompt_tokens: int, completion_tokens: int, endpoint: str = "chat"):
        db = SessionLocal()
        try:
            usage = TokenUsage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost=0,
                endpoint=endpoint,
                created_at=datetime.utcnow(),
            )
            db.add(usage)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record token usage: {e}")
            db.rollback()
        finally:
            db.close()

    def _should_degrade(self) -> bool:
        try:
            from harness.token_budget import token_budget_manager
            return token_budget_manager.should_degrade_model()
        except Exception:
            return False

    def _post_usage_tracking(self, tokens: int):
        try:
            from harness.token_budget import token_budget_manager
            token_budget_manager.record_usage(tokens)
        except Exception:
            pass

    async def chat(self, messages: list, model: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2000) -> str:
        cfg = self._get_config()
        if not cfg["api_key"]:
            return "AI 模型尚未配置，请在设置中填写 API Key。"

        target_model = model or cfg["model_primary"]
        if not model and self._should_degrade():
            target_model = cfg["model_fallback"]
            logger.info(f"Budget degradation: using fallback model {target_model}")
        try:
            result = await self._call_api(cfg["base_url"], cfg["api_key"], target_model, messages, temperature, max_tokens)
            return result
        except Exception as e:
            logger.warning(f"Primary model {target_model} failed: {e}, trying fallback")
            if target_model != cfg["model_fallback"]:
                try:
                    result = await self._call_api(cfg["base_url"], cfg["api_key"], cfg["model_fallback"], messages, temperature, max_tokens)
                    return result
                except Exception as e2:
                    logger.error(f"Fallback model also failed: {e2}")
                    return f"AI 调用失败：{str(e2)}"
            return f"AI 调用失败：{str(e)}"

    async def _call_api(self, base_url: str, api_key: str, model: str, messages: list, temperature: float, max_tokens: int) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            total = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            self._record_usage(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            self._post_usage_tracking(total)
            return content

    async def chat_with_tools(self, messages: list, tools: Optional[list] = None, model: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2000) -> dict:
        """Chat with optional tool/function calling. Returns either:
        - {"type": "text", "content": "..."} for direct responses
        - {"type": "tool_calls", "tool_calls": [...]} when model wants to call tools
        """
        cfg = self._get_config()
        if not cfg["api_key"]:
            return {"type": "text", "content": "AI 模型尚未配置，请在设置中填写 API Key。"}

        target_model = model or cfg["model_primary"]
        if not model and self._should_degrade():
            target_model = cfg["model_fallback"]
        body: dict = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{cfg['base_url']}/chat/completions",
                    headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                msg = choice["message"]
                usage = data.get("usage", {})
                total_toks = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                self._record_usage(target_model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
                self._post_usage_tracking(total_toks)

                if msg.get("tool_calls"):
                    return {"type": "tool_calls", "tool_calls": msg["tool_calls"]}
                return {"type": "text", "content": msg.get("content", "")}
        except Exception as e:
            logger.warning(f"chat_with_tools failed with {target_model}: {e}")
            if target_model != cfg["model_fallback"]:
                body["model"] = cfg["model_fallback"]
                if tools:
                    del body["tools"]
                    if "tool_choice" in body:
                        del body["tool_choice"]
                try:
                    async with httpx.AsyncClient(timeout=60) as client:
                        resp = await client.post(
                            f"{cfg['base_url']}/chat/completions",
                            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
                            json=body,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        content = data["choices"][0]["message"].get("content", "")
                        return {"type": "text", "content": content}
                except Exception as e2:
                    logger.error(f"Fallback also failed: {e2}")
            return {"type": "text", "content": f"AI 调用失败：{str(e)}"}

    async def chat_stream(self, messages: list, model: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 2000) -> AsyncGenerator[str, None]:
        cfg = self._get_config()
        if not cfg["api_key"]:
            yield "AI 模型尚未配置。"
            return
        target_model = model or cfg["model_primary"]
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{cfg['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
                json={"model": target_model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            continue

ai_client = AIClient()
