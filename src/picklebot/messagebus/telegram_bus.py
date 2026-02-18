"""Telegram message bus implementation."""

import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from picklebot.messagebus.base import MessageBus, TelegramContext
from picklebot.utils.config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramBus(MessageBus[TelegramContext]):
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

    def is_allowed(self, context: TelegramContext) -> bool:
        """Check if sender is whitelisted."""
        if not self.config.allowed_user_ids:
            return True
        return context.user_id in self.config.allowed_user_ids

    async def start(
        self, on_message: Callable[[str, TelegramContext], Awaitable[None]]
    ) -> None:
        """Start listening for Telegram messages."""
        logger.info(f"Message bus enabled with platform: {self.platform_name}")
        self.application = Application.builder().token(self.config.bot_token).build()

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle incoming Telegram message."""
            if (
                update.message
                and update.message.text
                and update.effective_chat
                and update.message.from_user
            ):
                # Extract user_id (the person) and chat_id (the conversation)
                user_id = str(update.message.from_user.id)
                chat_id = str(update.effective_chat.id)
                message = update.message.text

                logger.info(f"Received Telegram message from user {user_id} in chat {chat_id}")

                ctx = TelegramContext(user_id=user_id, chat_id=chat_id)

                try:
                    await on_message(message, ctx)
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

    async def reply(self, content: str, context: TelegramContext) -> None:
        """Reply to incoming message."""
        if not self.application:
            raise RuntimeError("TelegramBus not started")

        try:
            await self.application.bot.send_message(
                chat_id=int(context.chat_id), text=content
            )
            logger.debug(f"Sent Telegram reply to {context.chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram reply: {e}")
            raise

    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message to default_chat_id."""
        if not self.application:
            raise RuntimeError("TelegramBus not started")

        # For now, ignore target parameter (future: support "user:123" format)
        if not self.config.default_chat_id:
            raise ValueError("No default_chat_id configured")

        try:
            await self.application.bot.send_message(
                chat_id=int(self.config.default_chat_id), text=content
            )
            logger.debug(f"Sent Telegram post to {self.config.default_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram post: {e}")
            raise

    async def stop(self) -> None:
        """Stop Telegram bot and cleanup."""
        if self.application:
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("TelegramBus stopped")
