"""MessageBusFrontend for posting messages to messagebus platform."""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

from picklebot.frontend.base import Frontend

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)


class MessageBusFrontend(Frontend):
    """Frontend that posts messages to messagebus platform."""

    def __init__(self, bus: "MessageBus", context: Any):
        """
        Initialize MessageBusFrontend.

        Args:
            bus: MessageBus instance for posting messages
            context: Platform-specific context for routing messages
        """
        self.bus = bus
        self.context = context

    async def show_welcome(self) -> None:
        """No-op for messagebus - no welcome on incoming messages."""
        pass

    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        """Send message via bus.reply() with error isolation."""
        if agent_id:
            content = f"[{agent_id}]: {content}"
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")

    async def show_system_message(self, content: str) -> None:
        """Send system message via bus.reply() with error isolation."""
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send system message: {e}")

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """No-op for messagebus - no transient display."""
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Send dispatch start notification."""
        msg = f"{calling_agent}: @{target_agent.lower()} {task}"
        try:
            await self.bus.reply(msg, self.context)
        except Exception as e:
            logger.warning(f"Failed to send dispatch notification: {e}")
        yield
