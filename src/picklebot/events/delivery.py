# src/picklebot/events/delivery.py
import logging
import random
from typing import TYPE_CHECKING, Any

from .bus import EventBus
from .types import Event, EventType

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


class DeliveryWorker:
    """Worker that delivers outbound messages to platforms."""

    def __init__(self, context: "SharedContext"):
        self.context = context

    async def handle_event(self, event: Event) -> None:
        """Handle an outbound message event."""
        if event.type != EventType.OUTBOUND:
            return

        try:
            # Look up where to deliver
            platform_info = self._lookup_platform(event.session_id, event.metadata)
            platform = platform_info["platform"]

            # Get limit and chunk
            limit = PLATFORM_LIMITS.get(platform, float("inf"))
            if limit != float("inf"):
                limit = int(limit)
            chunks = chunk_message(
                event.content,
                int(limit) if limit != float("inf") else len(event.content),
            )

            # Deliver each chunk
            for chunk in chunks:
                await self._deliver(platform, platform_info, chunk)

            # Ack the event
            self.context.eventbus.ack(event)

            logger.info(
                f"Delivered message to {platform} for session {event.session_id}"
            )

        except Exception as e:
            logger.error(f"Failed to deliver message: {e}")
            # TODO: Retry logic with backoff

    def _lookup_platform(
        self, session_id: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Look up platform and delivery context for a session.

        Args:
            session_id: Session ID to look up (UUID format)
            metadata: Optional event metadata (may contain 'platform' for proactive msgs)

        Returns:
            Dict with platform info (platform, user_id, chat_id/channel_id)
        """
        # Check metadata for platform (proactive messages from tools)
        if metadata and "platform" in metadata:
            platform = metadata["platform"]
            return self._get_proactive_platform_info(platform)

        # Look in messagebus config for session -> platform mapping
        messagebus_config = self.context.config.messagebus

        # Check Telegram sessions
        if messagebus_config.telegram:
            sessions = messagebus_config.telegram.sessions
            for user_id, sess_id in sessions.items():
                if sess_id == session_id:
                    return {
                        "platform": "telegram",
                        "user_id": user_id,
                        "chat_id": messagebus_config.telegram.default_chat_id,
                    }

        # Check Discord sessions
        if messagebus_config.discord:
            sessions = messagebus_config.discord.sessions
            for user_id, sess_id in sessions.items():
                if sess_id == session_id:
                    return {
                        "platform": "discord",
                        "user_id": user_id,
                        "channel_id": messagebus_config.discord.default_chat_id,
                    }

        # Default to CLI if not found
        return {"platform": "cli"}

    def _get_proactive_platform_info(self, platform: str) -> dict[str, Any]:
        """Get platform info for proactive messages.

        Args:
            platform: Target platform name

        Returns:
            Dict with platform info for proactive delivery
        """
        messagebus_config = self.context.config.messagebus

        if platform == "telegram" and messagebus_config.telegram:
            return {
                "platform": "telegram",
                "chat_id": messagebus_config.telegram.default_chat_id,
            }
        elif platform == "discord" and messagebus_config.discord:
            return {
                "platform": "discord",
                "channel_id": messagebus_config.discord.default_chat_id,
            }

        # Default to CLI for unknown platforms
        return {"platform": "cli"}

    def _get_bus(self, platform: str) -> "MessageBus[Any] | None":
        """Get the message bus for a platform."""
        for bus in self.context.messagebus_buses:
            if bus.platform_name == platform:
                return bus
        return None

    async def _deliver(
        self, platform: str, platform_info: dict[str, Any], content: str
    ) -> None:
        """Deliver a message chunk to a platform."""
        bus = self._get_bus(platform)

        if platform == "telegram" and bus is not None:
            # Import here to avoid circular dependency
            from picklebot.messagebus.telegram_bus import TelegramContext

            chat_id = platform_info.get("chat_id")
            user_id = platform_info.get("user_id")
            if chat_id and user_id:
                ctx = TelegramContext(user_id=user_id, chat_id=chat_id)
                await bus.reply(content, ctx)
            elif chat_id:
                # Use post for proactive message to default chat
                await bus.post(content)

        elif platform == "discord" and bus is not None:
            # Import here to avoid circular dependency
            from picklebot.messagebus.discord_bus import DiscordContext

            channel_id = platform_info.get("channel_id")
            user_id = platform_info.get("user_id")
            if channel_id and user_id:
                ctx = DiscordContext(user_id=user_id, channel_id=channel_id)
                await bus.reply(content, ctx)
            elif channel_id:
                # Use post for proactive message to default channel
                await bus.post(content)

        elif platform == "cli":
            # CLI just prints to stdout
            print(content)

    def subscribe(self, eventbus: EventBus) -> None:
        """Subscribe this worker to an event bus."""
        eventbus.subscribe(EventType.OUTBOUND, self.handle_event)
