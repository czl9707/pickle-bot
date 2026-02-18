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


class TestDiscordBusSendMessageUserIdHandling:
    """Tests for send_message user_id handling."""

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "user_id,default_user_id,expected_channel_id,should_raise",
        [
            # Explicit user_id overrides default
            ("999888777", "111222333", 999888777, False),
            # Fallback to default when no user_id
            (None, "111222333", 111222333, False),
            # Error when neither provided
            (None, None, None, True),
        ],
        ids=["explicit_user_id", "fallback_to_default", "error_no_user_no_default"],
    )
    async def test_send_message_user_id_handling(
        self, user_id, default_user_id, expected_channel_id, should_raise
    ):
        """Test send_message handles user_id correctly in all cases."""
        config = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id=default_user_id,
        )
        bus = DiscordBus(config)

        # Mock the client and channel
        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        if should_raise:
            with pytest.raises(
                ValueError, match="No user_id provided and no default_user_id configured"
            ):
                await bus.send_message(content="Test message", user_id=user_id)
        else:
            await bus.send_message(content="Test message", user_id=user_id)

            mock_client.get_channel.assert_called_once_with(expected_channel_id)
            mock_channel.send.assert_called_once_with("Test message")
