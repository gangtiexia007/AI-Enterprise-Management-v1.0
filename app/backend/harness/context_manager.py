"""Conversation context management with window truncation."""
from typing import List, Dict

MAX_CONTEXT_MESSAGES = 20
MAX_CONTEXT_TOKENS_ESTIMATE = 4000

class ContextManager:
    def __init__(self, max_messages: int = MAX_CONTEXT_MESSAGES):
        self.max_messages = max_messages

    def build_context(self, history: List[Dict], system_prompt: str, data_context: str = "") -> List[Dict]:
        messages = [{"role": "system", "content": system_prompt}]
        if data_context:
            messages.append({"role": "system", "content": data_context})
        recent = history[-self.max_messages:] if len(history) > self.max_messages else history
        for msg in recent:
            messages.append({"role": msg["role"], "content": msg["content"]})
        return messages

    def truncate_if_needed(self, messages: List[Dict], max_chars: int = 16000) -> List[Dict]:
        total_chars = sum(len(m.get("content", "")) for m in messages)
        if total_chars <= max_chars:
            return messages
        system_msgs = [m for m in messages if m["role"] == "system"]
        conv_msgs = [m for m in messages if m["role"] != "system"]
        while total_chars > max_chars and len(conv_msgs) > 2:
            removed = conv_msgs.pop(0)
            total_chars -= len(removed.get("content", ""))
        return system_msgs + conv_msgs

    def summarize_for_memory(self, messages: List[Dict]) -> str:
        conv_parts = []
        for m in messages:
            if m["role"] != "system":
                role_label = "用户" if m["role"] == "user" else "AI"
                conv_parts.append(f"{role_label}: {m['content'][:100]}")
        return "\n".join(conv_parts[-10:])
