"""AgentLoop state machine for conversation management."""
import enum
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AgentState(str, enum.Enum):
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    RESPONDING = "responding"
    ERROR = "error"

class AgentLoop:
    def __init__(self):
        self.state = AgentState.IDLE
        self.current_task: Optional[str] = None

    def transition(self, new_state: AgentState):
        logger.debug(f"AgentLoop: {self.state} -> {new_state}")
        self.state = new_state

    async def process(self, user_input: str, context: dict) -> str:
        self.transition(AgentState.THINKING)
        try:
            if user_input.startswith("/"):
                self.transition(AgentState.TOOL_USE)
                result = await self._handle_command(user_input, context)
            else:
                self.transition(AgentState.RESPONDING)
                result = await self._handle_conversation(user_input, context)
            self.transition(AgentState.IDLE)
            return result
        except Exception as e:
            self.transition(AgentState.ERROR)
            logger.error(f"AgentLoop error: {e}")
            self.transition(AgentState.IDLE)
            raise

    async def _handle_command(self, command: str, context: dict) -> str:
        return context.get("command_handler", lambda c, ctx: "未知命令")(command, context)

    async def _handle_conversation(self, message: str, context: dict) -> str:
        ai_handler = context.get("ai_handler")
        if ai_handler:
            return await ai_handler(message, context)
        return "AI 未配置"
