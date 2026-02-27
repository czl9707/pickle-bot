"""MessageBusFrontend for posting messages to messagebus platforms."""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

from .base import Frontend

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)


class MessageBusFrontend(Frontend):
    """Frontend that posts messages to messagebus platforms (Telegram, Discord)."""

    def __init__(self, bus: "MessageBus[Any]", context: Any):
        self.bus = bus
        self.context = context

    async def show_welcome(self) -> None:
        """No welcome message for messagebus - incoming message triggered."""
        pass

    async def show_message(self, content: str, agent_id: str | None = None) -> None:
        """Send message via bus.reply() with agent context prefix."""
        if agent_id:
            content = f"[{agent_id}]: {content}"
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")

    async def show_system_message(self, content: str) -> None:
        """Send system message via bus.reply()."""
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send system message: {e}")

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """No transient display for messagebus platforms."""
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Send dispatch notification via bus.reply()."""
        msg = f"{calling_agent}: @{target_agent.lower()} {task}"
        try:
            await self.bus.reply(msg, self.context)
        except Exception as e:
            logger.warning(f"Failed to send dispatch notification: {e}")
        yield
