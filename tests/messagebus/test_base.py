"""Tests for MessageBus abstract interface."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from typing import Any

from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus, TelegramEventSource
from picklebot.messagebus.discord_bus import DiscordBus, DiscordEventSource
from picklebot.utils.config import (
    TelegramConfig,
    DiscordConfig,
    MessageBusConfig,
    Config,
    LLMConfig,
)


def _create_mock_telegram_app():
    """Create a mock Telegram Application for testing."""
    mock_app = MagicMock()
    mock_app.updater = MagicMock()
    mock_app.updater.running = True
    mock_app.updater.start_polling = AsyncMock()
    mock_app.updater.stop = AsyncMock()
    mock_app.initialize = AsyncMock()
    mock_app.start = AsyncMock()
    mock_app.stop = AsyncMock()
    mock_app.shutdown = AsyncMock()
    mock_app.add_handler = MagicMock()
    mock_app.bot = MagicMock()
    return mock_app


def _create_mock_discord_client():
    """Create a mock Discord Client for testing."""
    mock_client = MagicMock()
    mock_client.start = AsyncMock()
    mock_client.close = AsyncMock()
    return mock_client


class MockBus(MessageBus[Any]):
    """Mock implementation for testing."""

    @property
    def platform_name(self) -> str:
        return "mock"

    async def run(self, on_message) -> None:
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
            lambda user_id: TelegramEventSource(user_id=user_id, chat_id="123"),
        ),
        (
            "discord",
            lambda: DiscordConfig(
                bot_token="test-token", allowed_user_ids=["whitelisted"]
            ),
            lambda user_id: DiscordEventSource(user_id=user_id, channel_id="123"),
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
            telegram=TelegramConfig(enabled=False, bot_token="test_token"),
        ),
    )
    buses = MessageBus.from_config(config)

    assert len(buses) == 0


class TestEventSourceDataclasses:
    """Tests for platform EventSource dataclasses."""

    def test_telegram_event_source_fields(self):
        """TelegramEventSource should have user_id and chat_id."""
        source = TelegramEventSource(user_id="111", chat_id="222")
        assert source.user_id == "111"
        assert source.chat_id == "222"

    def test_discord_event_source_fields(self):
        """DiscordEventSource should have user_id and channel_id."""
        source = DiscordEventSource(user_id="333", channel_id="444")
        assert source.user_id == "333"
        assert source.channel_id == "444"


@pytest.mark.parametrize("bus_type", ["telegram", "discord"])
class TestMessageBusLifecycle:
    """Shared lifecycle tests for all bus implementations."""

    @pytest.mark.anyio
    async def test_stop_without_run_is_safe(self, bus_type):
        """Calling stop without run should be safe - no-op."""
        if bus_type == "telegram":
            config = TelegramConfig(bot_token="test_token")
            bus = TelegramBus(config)
        else:
            config = DiscordConfig(bot_token="test_token")
            bus = DiscordBus(config)

        await bus.stop()  # Should not raise
