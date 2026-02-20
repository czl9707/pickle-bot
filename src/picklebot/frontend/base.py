"""Abstract base class for frontend implementations."""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator


class Frontend(ABC):
    """Abstract interface for frontend implementations."""

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
