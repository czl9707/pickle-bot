"""Abstract base class for message bus implementations."""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Generic, TypeVar, Any

from picklebot.utils.config import Config


class MessageContext(ABC):
    """Abstract base for message context."""

    pass


T = TypeVar("T", bound=MessageContext)


class MessageBus(ABC, Generic[T]):
    """Abstract base for messaging platforms with platform-specific context."""

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
            on_message: Callback async function(message: str, context: T)

        Raises:
            RuntimeError: If run() is called when already running.
        """
        pass

    @abstractmethod
    def is_allowed(self, context: T) -> bool:
        """
        Check if sender is whitelisted.

        Args:
            context: Platform-specific message context

        Returns:
            True if sender is allowed
        """
        pass

    @abstractmethod
    async def reply(self, content: str, context: T) -> None:
        """
        Reply to incoming message.

        Args:
            content: Message content to send
            context: Platform-specific context from incoming message
        """
        pass

    @abstractmethod
    async def post(self, content: str, target: str | None = None) -> None:
        """
        Post proactive message to default destination or specific target.

        Args:
            content: Message content to send
            target: Optional target (e.g., "user:123", "channel:456")
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and cleanup resources."""
        pass

    @staticmethod
    def from_config(config: Config) -> list["MessageBus[Any]"]:
        """
        Create message bus instances from configuration.

        Args:
            config: Message bus configuration

        Returns:
            List of configured message bus instances
        """
        # Inline imports to avoid circular dependency
        from picklebot.messagebus.telegram_bus import TelegramBus
        from picklebot.messagebus.discord_bus import DiscordBus

        buses: list["MessageBus[Any]"] = []
        bus_config = config.messagebus
        if bus_config.telegram and bus_config.telegram.enabled:
            buses.append(TelegramBus(bus_config.telegram))

        if bus_config.discord and bus_config.discord.enabled:
            buses.append(DiscordBus(bus_config.discord))

        return buses
