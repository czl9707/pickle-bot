"""Tests for DiscordBus."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from picklebot.messagebus.discord_bus import DiscordBus
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

    # Should not raise
    await bus.start(lambda msg, plat, uid: None)
    # Note: Discord bot needs event loop to fully start, so we just test it doesn't crash
    await bus.stop()


class TestDiscordBusDefaultUser:
    """Tests for default user ID fallback."""

    @pytest.mark.anyio
    async def test_send_message_falls_back_to_default(self):
        """When user_id is None, should send to default_user_id."""
        config = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="111222333",
        )
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        # Call without user_id
        await bus.send_message(content="Test message")

        # Should have called with default user_id
        mock_client.get_channel.assert_called_once_with(111222333)
        mock_channel.send.assert_called_once_with("Test message")

    @pytest.mark.anyio
    async def test_send_message_uses_provided_user_id(self):
        """When user_id is provided, should use it instead of default."""
        config = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="111222333",
        )
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        # Call with explicit user_id
        await bus.send_message(content="Test message", user_id="999888777")

        # Should have called with provided user_id
        mock_client.get_channel.assert_called_once_with(999888777)
        mock_channel.send.assert_called_once_with("Test message")

    @pytest.mark.anyio
    async def test_send_message_raises_without_user_id_or_default(self):
        """Should raise ValueError when no user_id and no default configured."""
        config = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id=None,
        )
        bus = DiscordBus(config)

        # Mock the client
        mock_client = MagicMock()
        bus.client = mock_client

        # Should raise ValueError
        with pytest.raises(ValueError, match="No user_id provided and no default_user_id configured"):
            await bus.send_message(content="Test message")
