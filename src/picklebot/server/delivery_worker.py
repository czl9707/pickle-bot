"""Worker that delivers outbound messages to platforms."""

import logging
import random
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from picklebot.core.events import EventSource, OutboundEvent
from picklebot.core.history import HistorySession
from .worker import SubscriberWorker

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)

# Retry configuration
BACKOFF_MS = [5000, 25000, 120000, 600000]  # 5s, 25s, 2min, 10min
MAX_RETRIES = 5


def compute_backoff_ms(retry_count: int) -> int:
    """Compute backoff time with jitter.

    Args:
        retry_count: Current retry attempt (1-indexed)

    Returns:
        Backoff time in milliseconds
    """
    if retry_count <= 0:
        return 0

    # Cap at last backoff value
    idx = min(retry_count - 1, len(BACKOFF_MS) - 1)
    base = BACKOFF_MS[idx]

    # Add +/- 20% jitter
    jitter = random.randint(-base // 5, base // 5)
    return max(0, base + jitter)


# Platform message size limits
PLATFORM_LIMITS: dict[str, float] = {
    "telegram": 4096,
    "discord": 2000,
    "cli": float("inf"),  # no limit
}


def chunk_message(content: str, limit: int) -> list[str]:
    """Split message at paragraph boundaries, respecting limit.

    Args:
        content: The message to chunk
        limit: Maximum characters per chunk

    Returns:
        List of message chunks
    """
    if len(content) <= limit:
        return [content]

    chunks = []
    paragraphs = content.split("\n\n")
    current = ""

    for para in paragraphs:
        # Try to add to current chunk
        if current:
            potential = current + "\n\n" + para
        else:
            potential = para

        if len(potential) <= limit:
            current = potential
        else:
            # Current chunk is complete
            if current:
                chunks.append(current)

            # Handle paragraph that exceeds limit
            if len(para) > limit:
                # Hard split
                for i in range(0, len(para), limit):
                    chunks.append(para[i : i + limit])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


class DeliveryWorker(SubscriberWorker):
    """Worker that delivers outbound messages to platforms."""

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.context.eventbus.subscribe(OutboundEvent, self.handle_event)
        self.logger.info("DeliveryWorker subscribed to OUTBOUND events")

    @lru_cache(maxsize=10)
    def _get_session_source(self, session_id: str) -> HistorySession | None:
        """Get session info from HistoryStore (cached)."""
        for session in self.context.history_store.list_sessions():
            if session.id == session_id:
                return session
        return None

    async def handle_event(self, event: OutboundEvent) -> None:
        """Handle an outbound message event."""
        try:
            session_info = self._get_session_source(event.session_id)

            if not session_info or not session_info.source:
                self.logger.warning(
                    f"No source for session {event.session_id}, skipping delivery"
                )
                return

            # Get typed EventSource from stored string
            source = session_info.get_source()

            # Get platform name from source
            platform = source.platform_name
            if not platform:
                # Try default delivery source for agent/cron events
                default_source_str = self.context.config.default_delivery_source
                if default_source_str:
                    try:
                        source = EventSource.from_string(default_source_str)
                        platform = source.platform_name
                        if not platform:
                            self.logger.error(
                                f"default_delivery_source '{default_source_str}' is not a platform source"
                            )
                            return
                    except ValueError as e:
                        self.logger.error(f"Invalid default_delivery_source: {e}")
                        return
                else:
                    self.logger.warning(
                        f"No platform for session {event.session_id} and no default_delivery_source configured"
                    )
                    return

            limit = PLATFORM_LIMITS.get(platform, float("inf"))
            if limit != float("inf"):
                limit = int(limit)
            chunks = chunk_message(
                event.content,
                int(limit) if limit != float("inf") else len(event.content),
            )

            bus = self._get_bus(platform)
            if bus:
                for chunk in chunks:
                    await bus.reply(chunk, source)

            self.context.eventbus.ack(event)
            self.logger.info(
                f"Delivered message to {platform} for session {event.session_id}"
            )

        except Exception as e:
            self.logger.error(f"Failed to deliver message: {e}")

    def _get_bus(self, platform: str) -> "MessageBus[Any] | None":
        """Get the message bus for a platform."""
        for bus in self.context.messagebus_buses:
            if bus.platform_name == platform:
                return bus
        return None
