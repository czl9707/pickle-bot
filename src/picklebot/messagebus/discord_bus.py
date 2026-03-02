"""Discord message bus implementation."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Callable, Awaitable

import discord

from picklebot.core.events import EventSource
from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import DiscordConfig

logger = logging.getLogger(__name__)


@dataclass
class DiscordEventSource(EventSource):
    """Source for Discord-originated events."""

    _namespace = "platform-discord"
    user_id: str
    channel_id: str

    def __str__(self) -> str:
        return f"platform-discord:{self.user_id}:{self.channel_id}"

    @classmethod
    def from_string(cls, s: str) -> "DiscordEventSource":
        _, user_id, channel_id = s.split(":")
        return cls(user_id=user_id, channel_id=channel_id)

    @property
    def platform_name(self) -> str:
        return "discord"


class DiscordBus(MessageBus[DiscordEventSource]):
    """Discord platform implementation using discord.py."""

    platform_name = "discord"

    def __init__(self, config: DiscordConfig):
        """
        Initialize DiscordBus.

        Args:
            config: Discord configuration
        """
        self.config = config
        self.client: discord.Client | None = None
        self._running_task: asyncio.Task | None = None

    async def run(
        self, on_message: Callable[[str, DiscordEventSource], Awaitable[None]]
    ) -> None:
        """Run the Discord message bus. Blocks until stop() is called.

        Raises:
            RuntimeError: If run() is called when already running.
        """
        if self._running_task is not None:
            raise RuntimeError("DiscordBus already running")

        logger.info(f"Message bus enabled with platform: {self.platform_name}")

        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        @self.client.event
        async def _on_discord_message(message: discord.Message) -> None:
            """Handle incoming Discord message."""
            # Ignore bot's own messages
            if self.client and message.author == self.client.user:
                return

            # Check channel restriction (optional)
            if (
                self.config.channel_id
                and str(message.channel.id) != self.config.channel_id
            ):
                return

            # Only handle text messages
            if not message.content:
                return

            # Extract user_id (the person) and channel_id (the channel)
            user_id = str(message.author.id)
            channel_id = str(message.channel.id)
            content = message.content

            logger.info(
                f"Received Discord message from user {user_id} in channel {channel_id}"
            )

            source = DiscordEventSource(user_id=user_id, channel_id=channel_id)

            try:
                await on_message(content, source)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Start the bot and store the task
        self._running_task = asyncio.create_task(
            self.client.start(self.config.bot_token)
        )

        logger.info("DiscordBus started")
        await self._running_task

    def is_allowed(self, source: DiscordEventSource) -> bool:
        """Check if sender is whitelisted."""
        if not self.config.allowed_user_ids:
            return True
        return source.user_id in self.config.allowed_user_ids

    async def reply(self, content: str, source: DiscordEventSource) -> None:
        """Reply to incoming message in the same channel."""
        if not self.client:
            raise RuntimeError("DiscordBus not started")

        try:
            channel = self.client.get_channel(int(source.channel_id))
            if not channel:
                raise ValueError(f"Channel {source.channel_id} not found")

            # Type ignore: discord.py returns a union, but we know text channels have send()
            await channel.send(content)  # type: ignore[union-attr]
            logger.debug(f"Sent Discord reply to {source.channel_id}")
        except Exception as e:
            logger.error(f"Failed to send Discord reply: {e}")
            raise

    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message to target or raise if not configured."""
        if not self.client:
            raise RuntimeError("DiscordBus not started")

        # For now, ignore target parameter (future: support "user:123" or "channel:456")
        # post() requires a target to be specified
        raise ValueError(
            "post() requires a target parameter. "
            "Proactive messages should use the DeliveryWorker with OutboundEvent."
        )

    async def stop(self) -> None:
        """Stop Discord bot and cleanup."""
        # Idempotent: skip if not running
        if self.client is None:
            logger.debug("DiscordBus not running, skipping stop")
            return

        await self.client.close()

        # Wait for running task to complete
        if self._running_task and not self._running_task.done():
            try:
                await asyncio.wait_for(self._running_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Running task did not complete in time")
            except Exception:
                pass  # Task may have already failed

        self.client = None
        self._running_task = None
        logger.info("DiscordBus stopped")
