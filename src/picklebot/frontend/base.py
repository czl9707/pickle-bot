"""Abstract base class for frontend implementations."""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

if TYPE_CHECKING:
    from picklebot.core.agent_loader import AgentDef
    from picklebot.messagebus.base import MessageBus


class Frontend(ABC):
    """Abstract interface for frontend implementations."""

    @staticmethod
    def for_bus(
        bus: "MessageBus[Any]", context: Any, agent_def: "AgentDef"
    ) -> "Frontend":
        """Factory method to create the appropriate frontend for a bus.

        Args:
            bus: The MessageBus instance
            context: Platform-specific context for routing messages
            agent_def: Agent definition for display purposes

        Returns:
            ConsoleFrontend for CLI platform (Rich formatting),
            MessageBusFrontend for others (calls bus.reply())
        """
        if bus.platform_name == "cli":
            from picklebot.frontend.console import ConsoleFrontend

            return ConsoleFrontend(agent_def)
        else:
            from picklebot.frontend.messagebus import MessageBusFrontend

            return MessageBusFrontend(bus, context)

    @abstractmethod
    async def show_welcome(self) -> None:
        """Display welcome message."""

    @abstractmethod
    async def show_message(self, content: str, agent_id: str | None = None) -> None:
        """Display a message with optional agent context."""

    @abstractmethod
    async def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""

    @abstractmethod
    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        yield

    @abstractmethod
    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Display subagent dispatch notification."""
        yield


class SilentFrontend(Frontend):
    """No-op frontend for unattended execution (e.g., cron jobs)."""

    async def show_welcome(self) -> None:
        pass

    async def show_message(self, content: str, agent_id: str | None = None) -> None:
        pass

    async def show_system_message(self, content: str) -> None:
        pass

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        yield
