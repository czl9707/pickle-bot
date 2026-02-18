"""Tests for MessageBus abstract interface."""

import pytest

from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import (
    TelegramConfig,
    DiscordConfig,
    MessageBusConfig,
    Config,
    LLMConfig,
)


class MockBus(MessageBus):
    """Mock implementation for testing."""

    @property
    def platform_name(self) -> str:
        return "mock"

    async def start(self, on_message) -> None:
        pass

    async def send_message(self, content: str, user_id: str | None = None) -> None:
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
    await bus.send_message("test message", user_id="user123")
    # Should not raise


def test_messagebus_from_config_empty(tmp_path):
    """Test from_config returns empty list when no buses configured."""
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        messagebus=MessageBusConfig(enabled=False),
    )
    buses = MessageBus.from_config(config)
    assert buses == []


def test_messagebus_from_config_telegram(tmp_path):
    """Test from_config creates TelegramBus when configured."""
    telegram_config = TelegramConfig(enabled=True, bot_token="test_token")
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=telegram_config,
        ),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 1
    assert isinstance(buses[0], TelegramBus)
    assert buses[0].config == telegram_config


def test_messagebus_from_config_discord(tmp_path):
    """Test from_config creates DiscordBus when configured."""
    discord_config = DiscordConfig(enabled=True, bot_token="test_token")
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="discord",
            discord=discord_config,
        ),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 1
    assert isinstance(buses[0], DiscordBus)
    assert buses[0].config == discord_config


def test_messagebus_from_config_both(tmp_path):
    """Test from_config creates both buses when both configured."""
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(enabled=True, bot_token="test_token"),
            discord=DiscordConfig(enabled=True, bot_token="test_token"),
        ),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 2
    assert isinstance(buses[0], TelegramBus)
    assert isinstance(buses[1], DiscordBus)


def test_messagebus_from_config_disabled_platform(tmp_path):
    """Test from_config skips disabled platforms."""
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(enabled=False, bot_token="test_token"),
        ),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 0


class TestContextDataclasses:
    """Tests for platform context dataclasses."""

    def test_telegram_context_fields(self):
        """TelegramContext should have user_id and chat_id."""
        from picklebot.messagebus.base import TelegramContext

        ctx = TelegramContext(user_id="111", chat_id="222")
        assert ctx.user_id == "111"
        assert ctx.chat_id == "222"

    def test_discord_context_fields(self):
        """DiscordContext should have user_id and channel_id."""
        from picklebot.messagebus.base import DiscordContext

        ctx = DiscordContext(user_id="333", channel_id="444")
        assert ctx.user_id == "333"
        assert ctx.channel_id == "444"
