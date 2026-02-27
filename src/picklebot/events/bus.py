# src/picklebot/events/bus.py
import asyncio
import logging
from typing import Callable, Awaitable
from collections import defaultdict

from .types import Event, EventType

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Central event bus with subscription support."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        """Subscribe a handler to an event type."""
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.value} events")

    def unsubscribe(self, handler: Handler) -> None:
        """Remove a handler from all subscriptions."""
        for event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed handler from {event_type.value} events")

    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers of an event (waits for all handlers to complete)."""
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return

        # Fire all handlers concurrently and wait for completion
        tasks = []
        for handler in handlers:
            tasks.append(handler(event))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in event handler: {result}")
