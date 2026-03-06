"""Telegram message bus implementation."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from picklebot.core.events import EventSource
from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import TelegramConfig

logger = logging.getLogger(__name__)


@dataclass
class TelegramEventSource(EventSource):
    """Source for Telegram-originated events."""

    _namespace = "platform-telegram"
    user_id: str
    chat_id: str

    def __str__(self) -> str:
        return f"platform-telegram:{self.user_id}:{self.chat_id}"

    @classmethod
    def from_string(cls, s: str) -> "TelegramEventSource":
        _, user_id, chat_id = s.split(":")
        return cls(user_id=user_id, chat_id=chat_id)

    @property
    def platform_name(self) -> str:
        return "telegram"


class TelegramBus(MessageBus[TelegramEventSource]):
    """Telegram platform implementation using python-telegram-bot."""

    platform_name = "telegram"

    def __init__(self, config: TelegramConfig):
        """
        Initialize TelegramBus.

        Args:
            config: Telegram configuration
        """
        self.config = config
        self.application: Application | None = None
        self._running_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    def is_allowed(self, source: TelegramEventSource) -> bool:
        """Check if sender is whitelisted."""
        if not self.config.allowed_user_ids:
            return True
        return source.user_id in self.config.allowed_user_ids

    async def run(
        self, on_message: Callable[[str, TelegramEventSource], Awaitable[None]]
    ) -> None:
        """Run the Telegram message bus. Blocks until stop() is called.

        Raises:
            RuntimeError: If run() is called when already running.
        """
        if self.application is not None:
            raise RuntimeError("TelegramBus already running")

        logger.info(f"Message bus enabled with platform: {self.platform_name}")
        self.application = Application.builder().token(self.config.bot_token).build()
        self._stop_event = asyncio.Event()

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

                logger.info(
                    f"Received Telegram message from user {user_id} in chat {chat_id}"
                )

                source = TelegramEventSource(user_id=user_id, chat_id=chat_id)

                try:
                    await on_message(message, source)
                except Exception as e:
                    logger.error(f"Error in message callback: {e}")

        handler = MessageHandler(filters.TEXT, handle_message)
        self.application.add_handler(handler)

        # Start the bot
        await self.application.initialize()
        await self.application.start()
        if self.application.updater:
            await self.application.updater.start_polling()

        logger.info("TelegramBus started")

        # Create the running task that monitors for stop
        async def run_until_stopped():
            """Run until stop() is called or updater stops unexpectedly."""
            while self.application and self.application.updater:
                if self.application.updater.running:
                    if self._stop_event and self._stop_event.is_set():
                        return  # Graceful stop
                    await asyncio.sleep(1)
                else:
                    if self._stop_event and not self._stop_event.is_set():
                        raise RuntimeError("Telegram updater stopped unexpectedly")
                    return

        self._running_task = asyncio.create_task(run_until_stopped())
        await self._running_task

    async def reply(self, content: str, source: TelegramEventSource) -> None:
        """Reply to incoming message."""
        if not self.application:
            raise RuntimeError("TelegramBus not started")

        try:
            await self.application.bot.send_message(
                chat_id=int(source.chat_id), text=content
            )
            logger.debug(f"Sent Telegram reply to {source.chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram reply: {e}")
            raise

    async def stop(self) -> None:
        """Stop Telegram bot and cleanup."""
        # Idempotent: skip if not running
        if self.application is None:
            logger.debug("TelegramBus not running, skipping stop")
            return

        # Signal the running task to stop
        if self._stop_event:
            self._stop_event.set()

        if self.application.updater and self.application.updater.running:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

        # Wait for running task to complete
        if self._running_task and not self._running_task.done():
            try:
                await asyncio.wait_for(self._running_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Running task did not complete in time")
            except Exception:
                pass  # Task may have already failed

        self.application = None
        self._running_task = None
        self._stop_event = None
        logger.info("TelegramBus stopped")
