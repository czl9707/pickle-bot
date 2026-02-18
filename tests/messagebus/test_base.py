"""Tests for MessageBus abstract interface."""

import pytest
from typing import Any

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


class MockBus(MessageBus[Any]):
    """Mock implementation for testing."""

    @property
    def platform_name(self) -> str:
        return "mock"

    async def start(self, on_message) -> None:
        pass

    def is_allowed(self, context: Any) -> bool:
        return True

    async def reply(self, content: str, context: Any) -> None:
        pass

    async def post(self, content: str, target: str | None = None) -> None:
        pass

    async def stop(self) -> None:
        pass


def test_messagebus_has_platform_name():
    """Test that MessageBus has platform_name property."""
    bus = MockBus()
    assert bus.platform_name == "mock"


@pytest.mark.anyio
async def test_messagebus_reply_interface():
    """Test that reply can be called."""
    bus = MockBus()
    await bus.reply("test message", context={})
    # Should not raise


@pytest.mark.anyio
async def test_messagebus_post_interface():
    """Test that post can be called."""
    bus = MockBus()
    await bus.post("test message")
    # Should not raise


class TestMessageBusGenericInterface:
    """Tests for generic MessageBus interface."""

    def test_messagebus_is_generic(self):
        """MessageBus should be a Generic class."""
        from picklebot.messagebus.base import MessageBus

        # Should have generic type parameter
        assert hasattr(MessageBus, "__orig_bases__")

    def test_messagebus_has_is_allowed_method(self):
        """MessageBus should have is_allowed abstract method."""
        from picklebot.messagebus.base import MessageBus
        import inspect

        # Check is_allowed is an abstract method
        assert hasattr(MessageBus, "is_allowed")
        sig = inspect.signature(MessageBus.is_allowed)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "context" in params

    def test_messagebus_has_reply_method(self):
        """MessageBus should have reply abstract method."""
        from picklebot.messagebus.base import MessageBus
        import inspect

        assert hasattr(MessageBus, "reply")
        sig = inspect.signature(MessageBus.reply)
        params = list(sig.parameters.keys())
        assert "content" in params
        assert "context" in params

    def test_messagebus_has_post_method(self):
        """MessageBus should have post abstract method."""
        from picklebot.messagebus.base import MessageBus
        import inspect

        assert hasattr(MessageBus, "post")
        sig = inspect.signature(MessageBus.post)
        params = list(sig.parameters.keys())
        assert "content" in params


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


@pytest.mark.xfail(reason="TelegramBus needs update for new interface (Task 4)")
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


@pytest.mark.xfail(reason="DiscordBus needs update for new interface (Task 5)")
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


@pytest.mark.xfail(
    reason="TelegramBus and DiscordBus need update for new interface (Tasks 4 and 5)"
)
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
