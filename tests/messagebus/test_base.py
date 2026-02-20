"""Tests for MessageBus abstract interface."""

import pytest
from typing import Any

from picklebot.messagebus.base import MessageBus, TelegramContext, DiscordContext
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


@pytest.mark.parametrize(
    "bus_type,config_factory,context_factory",
    [
        (
            "telegram",
            lambda: TelegramConfig(
                bot_token="test-token", allowed_user_ids=["whitelisted"]
            ),
            lambda user_id: TelegramContext(user_id=user_id, chat_id="123"),
        ),
        (
            "discord",
            lambda: DiscordConfig(
                bot_token="test-token", allowed_user_ids=["whitelisted"]
            ),
            lambda user_id: DiscordContext(user_id=user_id, channel_id="123"),
        ),
    ],
)
class TestMessageBusIsAllowed:
    """Shared tests for is_allowed across all bus implementations."""

    def test_is_allowed_returns_true_for_whitelisted_user(
        self, bus_type, config_factory, context_factory
    ):
        """is_allowed should return True for whitelisted user."""
        config = config_factory()
        if bus_type == "telegram":
            bus = TelegramBus(config)
        else:
            bus = DiscordBus(config)

        ctx = context_factory("whitelisted")
        assert bus.is_allowed(ctx) is True

    def test_is_allowed_returns_false_for_non_whitelisted_user(
        self, bus_type, config_factory, context_factory
    ):
        """is_allowed should return False for non-whitelisted user."""
        config = config_factory()
        if bus_type == "telegram":
            bus = TelegramBus(config)
        else:
            bus = DiscordBus(config)

        ctx = context_factory("unknown")
        assert bus.is_allowed(ctx) is False

    def test_is_allowed_returns_true_when_whitelist_empty(
        self, bus_type, config_factory, context_factory
    ):
        """is_allowed should return True when whitelist is empty."""
        if bus_type == "telegram":
            config = TelegramConfig(bot_token="test-token", allowed_user_ids=[])
            bus = TelegramBus(config)
        else:
            config = DiscordConfig(bot_token="test-token", allowed_user_ids=[])
            bus = DiscordBus(config)

        ctx = context_factory("anyone")
        assert bus.is_allowed(ctx) is True


def test_messagebus_has_platform_name():
    """Test that MessageBus has platform_name property."""
    bus = MockBus()
    assert bus.platform_name == "mock"


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
