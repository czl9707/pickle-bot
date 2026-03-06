"""Worker that delivers outbound messages to platforms."""

import asyncio
import logging
import random
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from picklebot.core.events import EventSource, OutboundEvent
from picklebot.core.history import HistorySession
from .worker import SubscriberWorker

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.channel.base import Channel

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

    async def _deliver_with_retry(
        self, chunks: list[str], source: "EventSource", channel: "Channel[Any]"
    ) -> bool:
        """Deliver all chunks with retry logic. Returns True on success."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                for chunk in chunks:
                    await channel.reply(chunk, source)
                return True
            except Exception as e:
                if attempt < MAX_RETRIES:
                    backoff_ms = compute_backoff_ms(attempt)
                    self.logger.warning(
                        f"Delivery failed (attempt {attempt}/{MAX_RETRIES}), "
                        f"retrying in {backoff_ms}ms: {e}"
                    )
                    await asyncio.sleep(backoff_ms / 1000)
                else:
                    self.logger.error(
                        f"Delivery failed after {MAX_RETRIES} attempts: {e}"
                    )
                    return False
        return False

    @lru_cache(maxsize=10)
    def _get_session_source(self, session_id: str) -> HistorySession | None:
        """Get session info from HistoryStore (cached)."""
        for session in self.context.history_store.list_sessions():
            if session.id == session_id:
                return session
        return None

    def _get_delivery_source(
        self, session_info: HistorySession
    ) -> "EventSource | None":
        """Get the delivery source for a session.

        Returns the session's source if it has a platform, otherwise
        falls back to default_delivery_source config.
        """
        source = session_info.get_source()

        # If source already has a platform, use it
        if source.platform_name:
            return source

        # Try default delivery source for agent events
        default_source_str = self.context.config.default_delivery_source
        if default_source_str:
            try:
                source = EventSource.from_string(default_source_str)
                if not source.platform_name:
                    self.logger.error(
                        f"default_delivery_source '{default_source_str}' is not a platform source"
                    )
                    return None
                return source
            except ValueError as e:
                self.logger.error(f"Invalid default_delivery_source: {e}")
                return None
        else:
            self.logger.warning(
                f"No platform for session {session_info.id} and no default_delivery_source configured"
            )
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

            source = self._get_delivery_source(session_info)
            if not source or not source.platform_name:
                # No valid delivery source - don't ack, let event be retried
                return

            limit = PLATFORM_LIMITS.get(source.platform_name, float("inf"))
            chunks = chunk_message(
                event.content,
                int(limit) if limit != float("inf") else len(event.content),
            )

            channel = self._get_channel(source.platform_name)
            if channel:
                success = await self._deliver_with_retry(chunks, source, channel)
                if not success:
                    self.logger.error(f"Dropped message for session {event.session_id}")

            self.context.eventbus.ack(event)
            self.logger.info(
                f"Delivered message to {source.platform_name} for session {event.session_id}"
            )

        except Exception as e:
            self.logger.error(f"Failed to deliver message: {e}")

    def _get_channel(self, platform: str) -> "Channel[Any] | None":
        """Get the message channel for a platform."""
        for channel in self.context.channels:
            if channel.platform_name == platform:
                return channel
        return None
