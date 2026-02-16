"""Abstract base class for frontend implementations."""

from abc import ABC, abstractmethod
import contextlib
from typing import Iterator


class Frontend(ABC):
    """Abstract interface for frontend implementations."""

    @abstractmethod
    def show_welcome(self) -> None:
        """Display welcome message."""

    @abstractmethod
    def get_user_input(self) -> str:
        """Get user input."""

    @abstractmethod
    def show_agent_response(self, content: str) -> None:
        """Display agent's final response to user."""

    @abstractmethod
    def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""

    @abstractmethod
    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        yield


class SilentFrontend(Frontend):
    """No-op frontend for unattended execution (e.g., cron jobs)."""

    def show_welcome(self) -> None:
        pass

    def get_user_input(self) -> str:
        return ""

    def show_agent_response(self, content: str) -> None:
        pass

    def show_system_message(self, content: str) -> None:
        pass

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        yield
