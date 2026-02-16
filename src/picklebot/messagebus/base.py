"""Abstract base class for message bus implementations."""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class MessageBus(ABC):
    """Abstract base for messaging platforms."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Platform identifier.

        Returns:
            Platform name (e.g., 'telegram', 'discord')
        """
        pass

    @abstractmethod
    async def start(
        self, on_message: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """
        Start listening for messages.

        Args:
            on_message: Callback async function(message: str, platform: str, user_id: str)
        """
        pass

    @abstractmethod
    async def send_message(self, user_id: str, content: str) -> None:
        """
        Send message to specific user on this platform.

        Args:
            user_id: Platform-specific user identifier
            content: Message content to send
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and cleanup resources."""
        pass
