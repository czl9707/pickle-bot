"""Tests for DiscordBus."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from picklebot.messagebus.discord_bus import DiscordBus, DiscordEventSource
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
        """reply should send to source.channel_id."""
        config = DiscordConfig(bot_token="test-token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        bus.client = mock_client

        source = DiscordEventSource(user_id="user123", channel_id="456789")
        await bus.reply(content="Test reply", source=source)

        mock_client.get_channel.assert_called_once_with(456789)
        mock_channel.send.assert_called_once_with("Test reply")


def _create_mock_discord_client():
    """Create a mock Discord Client for testing."""
    mock_client = MagicMock()
    mock_client.start = AsyncMock()
    mock_client.close = AsyncMock()
    return mock_client


class TestDiscordBusRunStop:
    """Tests for run/stop behavior."""

    @pytest.mark.anyio
    async def test_run_stop_lifecycle(self):
        """Test that DiscordBus can run and stop."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client
        ):
            await bus.run(dummy_callback)
            await bus.stop()

            mock_client.start.assert_called_once()
            mock_client.close.assert_called_once()

    @pytest.mark.anyio
    async def test_run_raises_on_second_call(self):
        """Calling run twice should raise RuntimeError."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client
        ):
            await bus.run(dummy_callback)

            with pytest.raises(RuntimeError, match="DiscordBus already running"):
                await bus.run(dummy_callback)

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client
        ):
            await bus.run(dummy_callback)
            await bus.stop()
            await bus.stop()  # Second call should be no-op

            mock_client.close.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_run_is_safe(self):
        """Calling stop without run should be safe - no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        await bus.stop()  # Should not raise

    @pytest.mark.anyio
    async def test_can_rerun_after_stop(self):
        """Should be able to run again after stop."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)
        mock_client = _create_mock_discord_client()

        async def dummy_callback(content: str, source: DiscordEventSource) -> None:
            pass

        with patch(
            "picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client
        ):
            # First cycle
            await bus.run(dummy_callback)
            await bus.stop()

            mock_client.start.reset_mock()

            # Second cycle should work
            await bus.run(dummy_callback)
            mock_client.start.assert_called_once()
