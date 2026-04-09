"""Channels — inbound message routing and outbound IM delivery.

Public surface:
    - ``register_webhook_routes`` for FastAPI app setup
    - ``BotManager`` for credential and routing management
    - ``NotificationService`` for event-driven notifications
"""

from app.channels.router import register_webhook_routes, route_inbound_message, set_inbound_handler
from app.channels.bot_manager import BotManager
from app.channels.notification import NotificationService

__all__ = [
    "register_webhook_routes",
    "route_inbound_message",
    "set_inbound_handler",
    "BotManager",
    "NotificationService",
]
