"""Telegram message bus implementation."""

import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramBus(MessageBus):
    """Telegram platform implementation using python-telegram-bot."""

    def __init__(self, config: TelegramConfig):
        """
        Initialize TelegramBus.

        Args:
            config: Telegram configuration
        """
        self.config = config
        self.application: Application | None = None

    @property
    def platform_name(self) -> str:
        """Platform identifier."""
        return "telegram"

    async def start(
        self, on_message: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """
        Start listening for Telegram messages.

        Args:
            on_message: Callback for incoming messages
        """
        logger.info(f"Message bus enabled with platform: {self.platform_name}")
        self.application = Application.builder().token(self.config.bot_token).build()

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle incoming Telegram message."""
            if update.message and update.message.text and update.effective_chat:
                user_id = str(update.effective_chat.id)
                message = update.message.text

                logger.info(f"Received Telegram message from {user_id}")

                try:
                    await on_message(message, self.platform_name, user_id)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")

        # Add message handler
        handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        self.application.add_handler(handler)

        # Start the bot
        await self.application.initialize()
        await self.application.start()
        if self.application.updater:
            await self.application.updater.start_polling()

        logger.info("TelegramBus started")

    async def send_message(self, content: str, user_id: str | None = None) -> None:
        """
        Send message to Telegram user.

        Args:
            content: Message content
            user_id: Telegram chat ID (uses default_user_id if not provided)
        """
        if not self.application:
            raise RuntimeError("TelegramBus not started")

        # Fall back to default user if not provided
        target_user = user_id or self.config.default_user_id
        if not target_user:
            raise ValueError("No user_id provided and no default_user_id configured")

        try:
            await self.application.bot.send_message(
                chat_id=int(target_user), text=content
            )
            logger.debug(f"Sent Telegram message to {target_user}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            raise

    async def stop(self) -> None:
        """Stop Telegram bot and cleanup."""
        if self.application:
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("TelegramBus stopped")
