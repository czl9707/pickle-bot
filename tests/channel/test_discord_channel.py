"""Tests for DiscordChannel."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from picklebot.channel.discord_channel import DiscordChannel, DiscordEventSource
from picklebot.utils.config import DiscordConfig


class TestDiscordChannelReply:
    """Tests for DiscordChannel.reply method."""

    @pytest.mark.anyio
    async def test_reply_sends_to_channel_id(self):
        """reply should send to source.channel_id."""
        config = DiscordConfig(bot_token="test-token")
        channel = DiscordChannel(config)

        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        channel.client = mock_client

        source = DiscordEventSource(user_id="user123", channel_id="456789")
        await channel.reply(content="Test reply", source=source)

        mock_client.get_channel.assert_called_once_with(456789)
        mock_channel.send.assert_called_once_with("Test reply")


def _create_mock_discord_client():
    """Create a mock Discord Client for testing."""
    mock_client = MagicMock()
    mock_client.start = AsyncMock()
    mock_client.close = AsyncMock()
    return mock_client


class TestDiscordChannelRunStop:
    """Tests for run/stop behavior."""

    @pytest.mark.anyio
    async def test_run_stop_lifecycle(self):
        """Test that DiscordChannel can run and stop."""
        config = DiscordConfig(bot_token="test_token")
        channel = DiscordChannel(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.discord_channel.discord.Client", return_value=mock_client
        ):
            await channel.run(dummy_callback)
            await channel.stop()

            mock_client.start.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.anyio
    async def test_run_raises_on_second_call(self):
        """Calling run twice should raise RuntimeError."""
        config = DiscordConfig(bot_token="test_token")
        channel = DiscordChannel(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.discord_channel.discord.Client", return_value=mock_client
        ):
            await channel.run(dummy_callback)

            with pytest.raises(RuntimeError, match="DiscordChannel already running"):
                await channel.run(dummy_callback)

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
        config = DiscordConfig(bot_token="test_token")
        channel = DiscordChannel(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.discord_channel.discord.Client", return_value=mock_client
        ):
            await channel.run(dummy_callback)
            await channel.stop()
            await channel.stop()  # Second call should be no-op

            mock_client.close.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_run_is_safe(self):
        """Calling stop without run should be safe - no-op."""
        config = DiscordConfig(bot_token="test_token")
        channel = DiscordChannel(config)

        await channel.stop()  # Should not raise

    @pytest.mark.anyio
    async def test_can_rerun_after_stop(self):
        """Should be able to run again after stop."""
        config = DiscordConfig(bot_token="test_token")
        channel = DiscordChannel(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.discord_channel.discord.Client", return_value=mock_client
        ):
            # First cycle
            await channel.run(dummy_callback)
            await channel.stop()

            mock_client.start.reset_mock()

            # Second cycle should work
            await channel.run(dummy_callback)
            mock_client.start.assert_called_once()
