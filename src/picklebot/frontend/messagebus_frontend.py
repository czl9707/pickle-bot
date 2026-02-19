"""MessageBusFrontend for posting dispatch messages to messagebus platform."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Iterator

from picklebot.frontend.base import Frontend

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)


class MessageBusFrontend(Frontend):
    """Frontend that posts dispatch messages to messagebus platform."""

    def __init__(self, bus: "MessageBus", context: Any):
        """
        Initialize MessageBusFrontend.

        Args:
            bus: MessageBus instance for posting messages
            context: Platform-specific context for routing messages
        """
        self.bus = bus
        self.context = context

    def show_welcome(self) -> None:
        """No-op for messagebus."""
        pass

    def show_message(self, content: str) -> None:
        """No-op for messagebus (messages are handled separately)."""
        pass

    def show_system_message(self, content: str) -> None:
        """No-op for messagebus."""
        pass

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """No-op for messagebus."""
        yield

    def show_dispatch_start(self, calling_agent: str, target_agent: str, task: str) -> None:
        """
        Post dispatch start message to messagebus.

        Args:
            calling_agent: Name of the calling agent
            target_agent: Name of the target agent
            task: Task description
        """
        try:
            msg = f"{calling_agent}: @{target_agent.lower()} {task}"
            asyncio.create_task(self.bus.reply(msg, self.context))
        except Exception as e:
            logger.warning(f"Failed to post dispatch message: {e}")

    def show_dispatch_result(self, calling_agent: str, target_agent: str, result: str) -> None:
        """
        Post dispatch result message to messagebus.

        Args:
            calling_agent: Name of the calling agent
            target_agent: Name of the target agent
            result: Result from subagent
        """
        try:
            truncated = result[:200] + "..." if len(result) > 200 else result
            msg = f"{target_agent}: - {truncated}"
            asyncio.create_task(self.bus.reply(msg, self.context))
        except Exception as e:
            logger.warning(f"Failed to post dispatch result: {e}")
