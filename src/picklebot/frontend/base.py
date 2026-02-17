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
    def show_message(self, content: str) -> None:
        """Display a message (user or agent)."""

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

    def show_message(self, content: str) -> None:
        pass

    def show_system_message(self, content: str) -> None:
        pass

    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        yield
