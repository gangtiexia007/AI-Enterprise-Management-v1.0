"""F24: WeCom Channel — WebSocket long connection with auto-reconnect.

Uses wecom-aibot-python-sdk when available.  Falls back to a basic
WebSocket implementation for message parsing and reconnection.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

from app.core.enums import Channel, MessageType
from app.core.exceptions import ChannelConnectionFailed
from app.core.models import UnifiedMessage

logger = logging.getLogger(__name__)

MessageHandler = Callable[[UnifiedMessage], Coroutine[Any, Any, None]]

RECONNECT_BASE_DELAY = 2.0
RECONNECT_MAX_DELAY = 60.0


class WeComWSClient:
    """WebSocket-based WeCom bot client with auto-reconnect."""

    def __init__(
        self,
        ws_url: str,
        token: str = "",
        on_message: MessageHandler | None = None,
    ):
        self.ws_url = ws_url
        self.token = token
        self._on_message = on_message
        self._running = False
        self._task: asyncio.Task | None = None
        self._reconnect_delay = RECONNECT_BASE_DELAY

    async def start(self) -> None:
        """Start the WebSocket listener loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._connect_loop())
        logger.info("WeCom WS client started for %s", self.ws_url)

    async def stop(self) -> None:
        """Gracefully stop the connection."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("WeCom WS client stopped")

    async def _connect_loop(self) -> None:
        """Reconnect loop with exponential backoff."""
        while self._running:
            try:
                await self._listen()
                self._reconnect_delay = RECONNECT_BASE_DELAY
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "WeCom WS disconnected: %s — reconnecting in %.0fs",
                    exc, self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, RECONNECT_MAX_DELAY,
                )

    async def send_message(self, content: str, to_user: str = "") -> bool:
        """Send a text message through the WebSocket connection."""
        if not hasattr(self, '_ws') or self._ws is None:
            logger.warning("WeCom WS: cannot send — not connected")
            return False
        try:
            payload = json.dumps({
                "msgtype": "text",
                "text": {"content": content},
            }, ensure_ascii=False)
            await self._ws.send(payload)
            return True
        except Exception as e:
            logger.error("WeCom WS send failed: %s", e)
            return False

    async def _listen(self) -> None:
        """Connect and read messages in a loop."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed; WeCom WS disabled")
            self._running = False
            return

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with websockets.connect(self.ws_url, extra_headers=headers) as ws:
            self._ws = ws
            logger.info("WeCom WS connected: %s", self.ws_url)
            async for raw_message in ws:
                try:
                    data = json.loads(raw_message)
                    msg = self._parse_message(data)
                    if msg and self._on_message:
                        await self._on_message(msg)
                except json.JSONDecodeError:
                    logger.warning("Non-JSON WeCom message: %s", raw_message[:200])
                except Exception:
                    logger.error("Error processing WeCom message", exc_info=True)
        self._ws = None

    @staticmethod
    def _parse_message(data: dict[str, Any]) -> UnifiedMessage | None:
        """Convert raw WeCom WS payload into UnifiedMessage."""
        msg_type_raw = data.get("MsgType", data.get("msgtype", ""))
        sender_id = data.get("From", {}).get("UserId", data.get("user_id", ""))
        content = ""
        file_url = ""
        msg_type = MessageType.TEXT

        if msg_type_raw == "text":
            content = data.get("Content", data.get("text", {}).get("content", ""))
        elif msg_type_raw == "image":
            msg_type = MessageType.IMAGE
            file_url = data.get("Image", {}).get("MediaId", "")
        elif msg_type_raw == "file":
            msg_type = MessageType.FILE
            file_url = data.get("File", {}).get("MediaId", "")
        elif msg_type_raw == "event":
            return None
        else:
            content = json.dumps(data, ensure_ascii=False)

        if not sender_id:
            return None

        return UnifiedMessage(
            channel=Channel.WECOM,
            sender_id=sender_id,
            content=content,
            msg_type=msg_type,
            file_url=file_url,
            raw=data,
        )


class WeComManager:
    """Manage multiple WeCom WebSocket connections (one per team bot)."""

    _instance: WeComManager | None = None

    def __init__(self) -> None:
        self._clients: dict[str, WeComWSClient] = {}

    @classmethod
    def get_instance(cls) -> WeComManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start_for_team(
        self,
        team_id: str,
        ws_url: str,
        token: str = "",
    ) -> None:
        """Start a WS connection for a team's WeCom bot."""
        if team_id in self._clients:
            await self._clients[team_id].stop()

        async def handler(msg: UnifiedMessage) -> None:
            msg.team_id = team_id
            from app.channels.router import route_inbound_message
            await route_inbound_message(msg)

        client = WeComWSClient(ws_url=ws_url, token=token, on_message=handler)
        self._clients[team_id] = client
        await client.start()

    async def stop_for_team(self, team_id: str) -> None:
        client = self._clients.pop(team_id, None)
        if client:
            await client.stop()

    async def send_to_team(self, team_id: str, content: str) -> bool:
        client = self._clients.get(team_id)
        if client:
            return await client.send_message(content)
        return False

    async def stop_all(self) -> None:
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
