"""Tests for TelegramChannel."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from picklebot.channel.telegram_channel import TelegramChannel, TelegramEventSource
from picklebot.utils.config import TelegramConfig


class TestTelegramChannelReply:
    """Tests for TelegramChannel.reply method."""

    @pytest.mark.anyio
    async def test_reply_raises_when_not_started(self):
        """reply should raise when not started."""
        config = TelegramConfig(bot_token="test_token")
        channel = TelegramChannel(config)

        source = TelegramEventSource(user_id="user123", chat_id="456789")
        with pytest.raises(RuntimeError, match="TelegramChannel not started"):
            await channel.reply(content="Hello, world!", source=source)

    @pytest.mark.anyio
    async def test_reply_sends_to_chat_id(self):
        """reply should send to source.chat_id."""
        config = TelegramConfig(bot_token="test-token")
        channel = TelegramChannel(config)

        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        channel.application = mock_app

        source = TelegramEventSource(user_id="user123", chat_id="456789")
        await channel.reply(content="Test reply", source=source)

        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 456789
        assert call_args.kwargs["text"] == "Test reply"


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


class TestTelegramChannelRunStop:
    """Tests for run/stop behavior."""

    @pytest.mark.anyio
    async def test_run_stop_lifecycle(self):
        """Test that TelegramChannel can run and stop."""
        config = TelegramConfig(bot_token="test_token")
        channel = TelegramChannel(config)
        mock_app = _create_mock_telegram_app()

        async def dummy_callback(msg: str, source: TelegramEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.telegram_channel.Application.builder"
        ) as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            run_task = asyncio.create_task(channel.run(dummy_callback))
            await asyncio.sleep(0.1)
            await channel.stop()
            await run_task

            mock_app.initialize.assert_called_once()
            mock_app.start.assert_called_once()
            mock_app.updater.start_polling.assert_called_once()

    @pytest.mark.anyio
    async def test_run_raises_on_second_call(self):
        """Calling run twice should raise RuntimeError."""
        config = TelegramConfig(bot_token="test_token")
        channel = TelegramChannel(config)
        mock_app = _create_mock_telegram_app()

        async def dummy_callback(msg: str, source: TelegramEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.telegram_channel.Application.builder"
        ) as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            run_task = asyncio.create_task(channel.run(dummy_callback))
            await asyncio.sleep(0.1)

            with pytest.raises(RuntimeError, match="TelegramChannel already running"):
                await channel.run(dummy_callback)

            await channel.stop()
            await run_task

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
        config = TelegramConfig(bot_token="test_token")
        channel = TelegramChannel(config)
        mock_app = _create_mock_telegram_app()

        async def dummy_callback(msg: str, source: TelegramEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.telegram_channel.Application.builder"
        ) as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            run_task = asyncio.create_task(channel.run(dummy_callback))
            await asyncio.sleep(0.1)
            await channel.stop()
            await run_task
            await channel.stop()  # Second call should be no-op

            mock_app.stop.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_run_is_safe(self):
        """Calling stop without run should be safe - no-op."""
        config = TelegramConfig(bot_token="test_token")
        channel = TelegramChannel(config)

        await channel.stop()  # Should not raise

    @pytest.mark.anyio
    async def test_can_rerun_after_stop(self):
        """Should be able to run again after stop."""
        config = TelegramConfig(bot_token="test_token")
        channel = TelegramChannel(config)
        mock_app = _create_mock_telegram_app()

        async def dummy_callback(msg: str, source: TelegramEventSource) -> None:
            pass

        with patch(
            "picklebot.channel.telegram_channel.Application.builder"
        ) as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            # First cycle
            run_task = asyncio.create_task(channel.run(dummy_callback))
            await asyncio.sleep(0.1)
            await channel.stop()
            await run_task

            mock_app.initialize.reset_mock()

            # Second cycle should work
            run_task2 = asyncio.create_task(channel.run(dummy_callback))
            await asyncio.sleep(0.1)
            mock_app.initialize.assert_called_once()

            await channel.stop()
            await run_task2
