"""Tests for MessageBus abstract interface."""

import pytest
from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import TelegramConfig, DiscordConfig, MessageBusConfig


class MockBus(MessageBus):
    """Mock implementation for testing."""

    @property
    def platform_name(self) -> str:
        return "mock"

    async def start(self, on_message) -> None:
        pass

    async def send_message(self, user_id: str, content: str) -> None:
        pass

    async def stop(self) -> None:
        pass


def test_messagebus_has_platform_name():
    """Test that MessageBus has platform_name property."""
    bus = MockBus()
    assert bus.platform_name == "mock"


@pytest.mark.anyio
async def test_messagebus_send_message_interface():
    """Test that send_message can be called."""
    bus = MockBus()
    await bus.send_message("user123", "test message")
    # Should not raise


def test_messagebus_from_config_empty():
    """Test from_config returns empty list when no buses configured."""
    config = MessageBusConfig(enabled=False)
    buses = MessageBus.from_config(config)
    assert buses == []


def test_messagebus_from_config_telegram():
    """Test from_config creates TelegramBus when configured."""
    telegram_config = TelegramConfig(enabled=True, bot_token="test_token")
    config = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=telegram_config,
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 1
    assert isinstance(buses[0], TelegramBus)
    assert buses[0].config == telegram_config


def test_messagebus_from_config_discord():
    """Test from_config creates DiscordBus when configured."""
    discord_config = DiscordConfig(enabled=True, bot_token="test_token")
    config = MessageBusConfig(
        enabled=True,
        default_platform="discord",
        discord=discord_config,
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 1
    assert isinstance(buses[0], DiscordBus)
    assert buses[0].config == discord_config


def test_messagebus_from_config_both():
    """Test from_config creates both buses when both configured."""
    config = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(enabled=True, bot_token="test_token"),
        discord=DiscordConfig(enabled=True, bot_token="test_token"),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 2
    assert isinstance(buses[0], TelegramBus)
    assert isinstance(buses[1], DiscordBus)


def test_messagebus_from_config_disabled_platform():
    """Test from_config skips disabled platforms."""
    config = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(enabled=False, bot_token="test_token"),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 0
