"""Tests for DiscordBus."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from picklebot.messagebus.discord_bus import DiscordBus, DiscordContext
from picklebot.utils.config import DiscordConfig


def test_discord_bus_platform_name():
    """Test that DiscordBus has correct platform name."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)
    assert bus.platform_name == "discord"


@pytest.mark.anyio
async def test_discord_bus_start_stop():
    """Test that DiscordBus can start and stop."""
    config = DiscordConfig(bot_token="test_token")
    bus = DiscordBus(config)

    # Mock the discord.Client to avoid actual network calls
    mock_client = MagicMock()
    mock_client.start = AsyncMock()
    mock_client.close = AsyncMock()

    with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
        # Should not raise - callback now receives (content, context)
        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        await bus.start(dummy_callback)
        await bus.stop()

        # Verify lifecycle was called
        mock_client.start.assert_called_once()
        mock_client.close.assert_called_once()


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


class TestDiscordBusIdempotentStartStop:
    """Tests for idempotent start/stop behavior."""

    @pytest.mark.anyio
    async def test_start_is_idempotent(self):
        """Calling start twice should be safe - second call is no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            await bus.start(dummy_callback)
            await bus.start(dummy_callback)  # Second call should be no-op

            # Should only start once (the task is created once)
            mock_client.start.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            await bus.start(dummy_callback)
            await bus.stop()
            await bus.stop()  # Second call should be no-op

            # Should only close once
            mock_client.close.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_start_is_safe(self):
        """Calling stop without start should be safe - no-op."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        # Should not raise
        await bus.stop()

    @pytest.mark.anyio
    async def test_can_restart_after_stop(self):
        """Should be able to start again after stop."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            # First cycle
            await bus.start(dummy_callback)
            await bus.stop()

            # Reset mock counts
            mock_client.start.reset_mock()

            # Second cycle should work
            await bus.start(dummy_callback)
            mock_client.start.assert_called_once()


class TestDiscordBusRunningTask:
    """Tests for start() returning a running task."""

    @pytest.mark.anyio
    async def test_start_returns_task(self):
        """start() should return an asyncio.Task."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            import asyncio
            task = await bus.start(dummy_callback)

            assert isinstance(task, asyncio.Task)

            # Clean up
            await bus.stop()

    @pytest.mark.anyio
    async def test_start_returns_same_task_if_called_twice(self):
        """Calling start() twice should return the same task."""
        config = DiscordConfig(bot_token="test_token")
        bus = DiscordBus(config)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.close = AsyncMock()

        async def dummy_callback(content: str, context: DiscordContext) -> None:
            pass

        with patch("picklebot.messagebus.discord_bus.discord.Client", return_value=mock_client):
            task1 = await bus.start(dummy_callback)
            task2 = await bus.start(dummy_callback)

            assert task1 is task2

            # Clean up
            await bus.stop()
