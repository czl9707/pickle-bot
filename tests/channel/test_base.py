"""Tests for Channel abstract interface."""

import pytest
from typing import Any

from picklebot.channel.base import Channel
from picklebot.channel.telegram_channel import TelegramChannel, TelegramEventSource
from picklebot.channel.discord_channel import DiscordChannel, DiscordEventSource
from picklebot.utils.config import (
    TelegramConfig,
    DiscordConfig,
    ChannelConfig,
    Config,
    LLMConfig,
)


class MockChannel(Channel[Any]):
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
    "channel_type,config_factory,context_factory",
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
class TestChannelIsAllowed:
    """Shared tests for is_allowed across all channel implementations."""

    def test_is_allowed_returns_true_for_whitelisted_user(
        self, channel_type, config_factory, context_factory
    ):
        """is_allowed should return True for whitelisted user."""
        config = config_factory()
        if channel_type == "telegram":
            channel = TelegramChannel(config)
        else:
            channel = DiscordChannel(config)

        ctx = context_factory("whitelisted")
        assert channel.is_allowed(ctx) is True

    def test_is_allowed_returns_false_for_non_whitelisted_user(
        self, channel_type, config_factory, context_factory
    ):
        """is_allowed should return False for non-whitelisted user."""
        config = config_factory()
        if channel_type == "telegram":
            channel = TelegramChannel(config)
        else:
            channel = DiscordChannel(config)

        ctx = context_factory("unknown")
        assert channel.is_allowed(ctx) is False

    def test_is_allowed_returns_true_when_whitelist_empty(
        self, channel_type, config_factory, context_factory
    ):
        """is_allowed should return True when whitelist is empty."""
        if channel_type == "telegram":
            config = TelegramConfig(bot_token="test-token", allowed_user_ids=[])
            channel = TelegramChannel(config)
        else:
            config = DiscordConfig(bot_token="test-token", allowed_user_ids=[])
            channel = DiscordChannel(config)

        ctx = context_factory("anyone")
        assert channel.is_allowed(ctx) is True


def test_channel_from_config_empty(tmp_path):
    """Test from_config returns empty list when no channels configured."""
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        channel=ChannelConfig(enabled=False),
    )
    channels = Channel.from_config(config)
    assert channels == []


def test_channel_from_config_disabled_platform(tmp_path):
    """Test from_config skips disabled platforms."""
    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="test", model="test", api_key="test"),
        default_agent="test",
        channel=ChannelConfig(
            enabled=True,
            telegram=TelegramConfig(enabled=False, bot_token="test_token"),
        ),
    )
    channels = Channel.from_config(config)

    assert len(channels) == 0


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


@pytest.mark.parametrize("channel_type", ["telegram", "discord"])
class TestChannelLifecycle:
    """Shared lifecycle tests for all channel implementations."""

    @pytest.mark.anyio
    async def test_stop_without_run_is_safe(self, channel_type):
        """Calling stop without run should be safe - no-op."""
        if channel_type == "telegram":
            config = TelegramConfig(bot_token="test_token")
            channel = TelegramChannel(config)
        else:
            config = DiscordConfig(bot_token="test_token")
            channel = DiscordChannel(config)

        await channel.stop()  # Should not raise
