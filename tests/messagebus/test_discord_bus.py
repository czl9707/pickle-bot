"""Tests for DiscordBus."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.messagebus.base import DiscordContext
from picklebot.utils.config import DiscordConfig


def test_discord_bus_platform_name():
    """Test that DiscordBus has correct platform name."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)
    assert bus.platform_name == "discord"


@pytest.mark.asyncio
async def test_discord_bus_start_stop():
    """Test that DiscordBus can start and stop."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)

    # Should not raise - callback now receives (content, context)
    async def dummy_callback(content: str, context: DiscordContext) -> None:
        pass

    await bus.start(dummy_callback)
    # Note: Discord bot needs event loop to fully start, so we just test it doesn't crash
    await bus.stop()


class TestDiscordBusIsAllowed:
    """Tests for DiscordBus.is_allowed method."""

    def test_is_allowed_returns_true_for_whitelisted_user(self):
        """is_allowed should return True for whitelisted user."""
        config = DiscordConfig(
            bot_token="test-token",
            allowed_user_ids=["123456789"],
        )
        bus = DiscordBus(config)

        ctx = DiscordContext(user_id="123456789", channel_id="987654321")
        assert bus.is_allowed(ctx) is True

    def test_is_allowed_returns_false_for_non_whitelisted_user(self):
        """is_allowed should return False for non-whitelisted user."""
        config = DiscordConfig(
            bot_token="test-token",
            allowed_user_ids=["123456789"],
        )
        bus = DiscordBus(config)

        ctx = DiscordContext(user_id="999888777", channel_id="987654321")
        assert bus.is_allowed(ctx) is False

    def test_is_allowed_returns_true_when_whitelist_empty(self):
        """is_allowed should return True when whitelist is empty."""
        config = DiscordConfig(
            bot_token="test-token",
            allowed_user_ids=[],
        )
        bus = DiscordBus(config)

        ctx = DiscordContext(user_id="555666777", channel_id="987654321")
        assert bus.is_allowed(ctx) is True


class TestDiscordBusReply:
    """Tests for DiscordBus.reply method."""

    @pytest.mark.anyio
    async def test_reply_sends_to_channel_id(self):
        """reply should send to context.channel_id."""
        config = DiscordConfig(bot_token="test-token")
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        ctx = DiscordContext(user_id="user123", channel_id="456789")
        await bus.reply(content="Test reply", context=ctx)

        mock_client.get_channel.assert_called_once_with(456789)
        mock_channel.send.assert_called_once_with("Test reply")


class TestDiscordBusPost:
    """Tests for DiscordBus.post method."""

    @pytest.mark.anyio
    async def test_post_sends_to_default_chat_id(self):
        """post should send to config.default_chat_id."""
        config = DiscordConfig(bot_token="test-token", default_chat_id="999888")
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        await bus.post(content="Proactive message")

        mock_client.get_channel.assert_called_once_with(999888)
        mock_channel.send.assert_called_once_with("Proactive message")

    @pytest.mark.anyio
    async def test_post_raises_when_no_default_chat_id(self):
        """post should raise when no default_chat_id configured."""
        config = DiscordConfig(bot_token="test-token", default_chat_id=None)
        bus = DiscordBus(config)

        bus.client = MagicMock()  # Mark as started

        with pytest.raises(ValueError, match="No default_chat_id configured"):
            await bus.post(content="Test")
