"""Tests for DiscordBus."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from picklebot.messagebus.discord_bus import DiscordBus, DiscordContext
from picklebot.utils.config import DiscordConfig


def test_discord_bus_platform_name():
    """Test that DiscordBus has correct platform name."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)
    assert bus.platform_name == "discord"


class TestDiscordBusReply:
    """Tests for DiscordBus.reply method."""

    @pytest.mark.anyio
    async def test_reply_sends_to_channel_id(self):
        """reply should send to context.channel_id."""
        config = DiscordConfig(bot_token="test-token")
        bus = DiscordBus(config)

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
    async def test_post_raises_requires_target(self):
        """post should raise indicating it requires a target parameter."""
        config = DiscordConfig(bot_token="test-token")
        bus = DiscordBus(config)
        bus.client = MagicMock()

        with pytest.raises(ValueError, match="requires a target parameter"):
            await bus.post(content="Test")
