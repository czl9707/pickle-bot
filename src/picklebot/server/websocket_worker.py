# src/picklebot/server/websocket_worker.py
"""WebSocket worker for broadcasting events to connected clients."""

import logging
from typing import TYPE_CHECKING

from .worker import SubscriberWorker
from picklebot.events.types import Event, EventType

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class WebSocketWorker(SubscriberWorker):
    """Broadcasts events to WebSocket clients.

    Auto-subscribes to ALL event types.
    """

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self._clients: set = set()  # Future: set of WebSocket connections

        # Auto-subscribe to all event types
        for event_type in EventType:
            self.context.eventbus.subscribe(event_type, self.handle_event)
        self.logger.info(
            f"WebSocketWorker subscribed to all {len(EventType)} event types"
        )

    async def handle_event(self, event: Event) -> None:
        """Handle an event by broadcasting to WebSocket clients.

        TODO: Implement actual WebSocket broadcasting.
        For now, just logs the event.
        """
        self.logger.debug(f"WebSocket stub received {event.type.value} event")
