"""Discord message bus implementation."""

import asyncio
import logging
from typing import Callable, Awaitable

import discord

from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import DiscordConfig

logger = logging.getLogger(__name__)


class DiscordBus(MessageBus):
    """Discord platform implementation using discord.py."""

    def __init__(self, config: DiscordConfig):
        """
        Initialize DiscordBus.

        Args:
            config: Discord configuration
        """
        self.config = config
        self.client: discord.Client | None = None

    @property
    def platform_name(self) -> str:
        """Platform identifier."""
        return "discord"

    async def start(
        self, on_message: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """
        Start listening for Discord messages.

        Args:
            on_message: Callback for incoming messages
        """
        logger.info(f"Message bus enabled with platform: {self.platform_name}")

        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        @self.client.event
        async def _on_discord_message(message: discord.Message):
            """Handle incoming Discord message."""
            # Ignore bot's own messages
            if message.author == self.client.user:
                return

            # Check channel restriction
            if (
                self.config.channel_id
                and str(message.channel.id) != self.config.channel_id
            ):
                return

            # Only handle text messages
            if not message.content:
                return

            user_id = str(message.channel.id)
            content = message.content

            logger.info(f"Received Discord message from {user_id}")

            try:
                await on_message(content, self.platform_name, user_id)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

        # Start the bot in background
        asyncio.create_task(self.client.start(self.config.bot_token))

        # Wait a moment for client to initialize
        await asyncio.sleep(0.5)

        logger.info("DiscordBus started")

    async def send_message(self, user_id: str, content: str) -> None:
        """
        Send message to Discord channel.

        Args:
            user_id: Discord channel ID
            content: Message content
        """
        if not self.client:
            raise RuntimeError("DiscordBus not started")

        try:
            channel = self.client.get_channel(int(user_id))
            if not channel:
                raise ValueError(f"Channel {user_id} not found")

            await channel.send(content)
            logger.debug(f"Sent Discord message to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            raise

    async def stop(self) -> None:
        """Stop Discord bot and cleanup."""
        if self.client:
            await self.client.close()
            logger.info("DiscordBus stopped")
