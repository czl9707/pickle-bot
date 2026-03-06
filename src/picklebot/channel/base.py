"""Abstract base class for message bus implementations."""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Generic, TypeVar, Any

from picklebot.core.events import EventSource
from picklebot.utils.config import Config


T = TypeVar("T", bound=EventSource)


class Channel(ABC, Generic[T]):
    """Abstract base for messaging platforms with EventSource-based context."""

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
    async def run(self, on_message: Callable[[str, T], Awaitable[None]]) -> None:
        """
        Run the message bus. Blocks until stop() is called.

        Args:
            on_message: Callback async function(message: str, source: T)

        Raises:
            RuntimeError: If run() is called when already running.
        """
        pass

    @abstractmethod
    def is_allowed(self, source: T) -> bool:
        """
        Check if sender is whitelisted.

        Args:
            source: Platform-specific event source

        Returns:
            True if sender is allowed
        """
        pass

    @abstractmethod
    async def reply(self, content: str, source: T) -> None:
        """
        Reply to incoming message.

        Args:
            content: Message content to send
            source: Platform-specific event source from incoming message
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and cleanup resources."""
        pass

    @staticmethod
    def from_config(config: Config) -> list["Channel[Any]"]:
        """
        Create channel instances from configuration.

        Args:
            config: Message bus configuration

        Returns:
            List of configured message bus instances
        """
        # Inline imports to avoid circular dependency
        from picklebot.channel.telegram_channel import TelegramChannel
        from picklebot.channel.discord_channel import DiscordChannel

        buses: list["Channel[Any]"] = []
        bus_config = config.channels
        if bus_config.telegram and bus_config.telegram.enabled:
            buses.append(TelegramChannel(bus_config.telegram))

        if bus_config.discord and bus_config.discord.enabled:
            buses.append(DiscordChannel(bus_config.discord))

        return buses
