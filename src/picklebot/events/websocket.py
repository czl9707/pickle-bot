# src/picklebot/events/websocket.py
"""WebSocket worker for broadcasting events to connected clients.

This is a stub implementation. Future work:
- Accept WebSocket connections
- Maintain set of connected clients
- Subscribe to ALL event types (INBOUND, OUTBOUND, STATUS)
- Broadcast events as JSON to all connected clients
- Handle client connect/disconnect
"""

import logging
from typing import TYPE_CHECKING

from .types import Event, EventType
from .bus import EventBus

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class WebSocketWorker:
    """Stub worker for WebSocket event broadcasting.

    Future implementation:
    - Subscribe to all event types
    - Broadcast to connected WebSocket clients
    - No persistence needed (real-time only)
    """

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.logger = logging.getLogger("picklebot.events.WebSocketWorker")
        self._clients: set = set()  # Future: set of WebSocket connections

    async def handle_event(self, event: Event) -> None:
        """Handle an event by broadcasting to WebSocket clients.

        TODO: Implement actual WebSocket broadcasting.
        For now, just logs the event.
        """
        self.logger.debug(f"WebSocket stub received {event.type.value} event")

    def subscribe(self, eventbus: EventBus) -> None:
        """Subscribe to all event types."""
        eventbus.subscribe(EventType.INBOUND, self.handle_event)
        eventbus.subscribe(EventType.OUTBOUND, self.handle_event)
        eventbus.subscribe(EventType.STATUS, self.handle_event)
        self.logger.info("WebSocketWorker subscribed to all event types")
