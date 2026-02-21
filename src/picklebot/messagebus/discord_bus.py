"""Discord message bus implementation."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Callable, Awaitable

import discord

from picklebot.messagebus.base import MessageBus, MessageContext
from picklebot.utils.config import DiscordConfig

logger = logging.getLogger(__name__)


@dataclass
class DiscordContext(MessageContext):
    """Context for Discord messages."""

    user_id: str  # author.id - for whitelisting
    channel_id: str  # channel.id - for replying

class DiscordBus(MessageBus[DiscordContext]):
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
        self, on_message: Callable[[str, DiscordContext], Awaitable[None]]
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

            ctx = DiscordContext(user_id=user_id, channel_id=channel_id)

            try:
                await on_message(content, ctx)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Start the bot and store the task
        self._running_task = asyncio.create_task(self.client.start(self.config.bot_token))

        logger.info("DiscordBus started")
        await self._running_task

    def is_allowed(self, context: DiscordContext) -> bool:
        """Check if sender is whitelisted."""
        if not self.config.allowed_user_ids:
            return True
        return context.user_id in self.config.allowed_user_ids

    async def reply(self, content: str, context: DiscordContext) -> None:
        """Reply to incoming message in the same channel."""
        if not self.client:
            raise RuntimeError("DiscordBus not started")

        try:
            channel = self.client.get_channel(int(context.channel_id))
            if not channel:
                raise ValueError(f"Channel {context.channel_id} not found")

            # Type ignore: discord.py returns a union, but we know text channels have send()
            await channel.send(content)  # type: ignore[union-attr]
            logger.debug(f"Sent Discord reply to {context.channel_id}")
        except Exception as e:
            logger.error(f"Failed to send Discord reply: {e}")
            raise

    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message to default_chat_id."""
        if not self.client:
            raise RuntimeError("DiscordBus not started")

        # For now, ignore target parameter (future: support "user:123" or "channel:456")
        if not self.config.default_chat_id:
            raise ValueError("No default_chat_id configured")

        try:
            channel = self.client.get_channel(int(self.config.default_chat_id))
            if not channel:
                raise ValueError(f"Channel {self.config.default_chat_id} not found")

            # Type ignore: discord.py returns a union, but we know text channels have send()
            await channel.send(content)  # type: ignore[union-attr]
            logger.debug(f"Sent Discord post to {self.config.default_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Discord post: {e}")
            raise

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
