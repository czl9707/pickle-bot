"""Tests for TelegramBus."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from picklebot.messagebus.telegram_bus import TelegramBus, TelegramContext
from picklebot.utils.config import TelegramConfig


def test_telegram_bus_platform_name():
    """Test that TelegramBus has correct platform name."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)
    assert bus.platform_name == "telegram"


@pytest.mark.anyio
async def test_telegram_bus_run_stop():
    """Test that TelegramBus can run and stop."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)

    # Mock the Application
    mock_app = MagicMock()
    mock_app.updater = MagicMock()
    mock_app.updater.running = True  # Simulate running state after run
    mock_app.updater.start_polling = AsyncMock()
    mock_app.updater.stop = AsyncMock()
    mock_app.initialize = AsyncMock()
    mock_app.start = AsyncMock()
    mock_app.stop = AsyncMock()
    mock_app.shutdown = AsyncMock()
    mock_app.add_handler = MagicMock()
    mock_app.bot = MagicMock()

    with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
        mock_builder.return_value.token.return_value.build.return_value = mock_app

        # Should not raise - callback now receives (message, context)
        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        # Run run() in background since it blocks until stop() is called
        run_task = asyncio.create_task(bus.run(dummy_callback))

        # Wait for run to initialize
        await asyncio.sleep(0.1)

        await bus.stop()

        # Wait for run_task to complete
        await run_task

        # Verify lifecycle was called
        mock_app.initialize.assert_called_once()
        mock_app.start.assert_called_once()
        mock_app.updater.start_polling.assert_called_once()
        mock_app.updater.stop.assert_called_once()
        mock_app.stop.assert_called_once()
        mock_app.shutdown.assert_called_once()


class TestTelegramBusReplyNotStarted:
    """Tests for TelegramBus.reply when not started."""

    @pytest.mark.anyio
    async def test_reply_raises_when_not_started(self):
        """reply should raise when not started."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        ctx = TelegramContext(user_id="user123", chat_id="456789")
        with pytest.raises(RuntimeError, match="TelegramBus not started"):
            await bus.reply(content="Hello, world!", context=ctx)


class TestTelegramBusPostNotStarted:
    """Tests for TelegramBus.post when not started."""

    @pytest.mark.anyio
    async def test_post_raises_when_not_started(self):
        """post should raise when not started."""
        config = TelegramConfig(bot_token="test_token", default_chat_id="12345")
        bus = TelegramBus(config)

        with pytest.raises(RuntimeError, match="TelegramBus not started"):
            await bus.post(content="Hello, world!")


class TestTelegramBusReply:
    """Tests for TelegramBus.reply method."""

    @pytest.mark.anyio
    async def test_reply_sends_to_chat_id(self):
        """reply should send to context.chat_id."""
        config = TelegramConfig(bot_token="test-token")
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        # Use numeric strings for chat_id (Telegram uses numeric IDs)
        ctx = TelegramContext(user_id="user123", chat_id="456789")
        await bus.reply(content="Test reply", context=ctx)

        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 456789
        assert call_args.kwargs["text"] == "Test reply"


class TestTelegramBusPost:
    """Tests for TelegramBus.post method."""

    @pytest.mark.anyio
    async def test_post_sends_to_default_chat_id(self):
        """post should send to config.default_chat_id."""
        config = TelegramConfig(bot_token="test-token", default_chat_id="999888")
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        await bus.post(content="Proactive message")

        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 999888

    @pytest.mark.anyio
    async def test_post_raises_when_no_default_chat_id(self):
        """post should raise when no default_chat_id configured."""
        config = TelegramConfig(bot_token="test-token", default_chat_id=None)
        bus = TelegramBus(config)

        bus.application = MagicMock()  # Mark as started

        with pytest.raises(ValueError, match="No default_chat_id configured"):
            await bus.post(content="Test")


class TestTelegramBusRunStop:
    """Tests for run/stop behavior."""

    @pytest.mark.anyio
    async def test_run_raises_on_second_call(self):
        """Calling run twice should raise RuntimeError."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

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

        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            # Run run() in background since it blocks
            run_task = asyncio.create_task(bus.run(dummy_callback))
            await asyncio.sleep(0.1)  # Let run() initialize

            # Second call should raise immediately (not in background)
            with pytest.raises(RuntimeError, match="TelegramBus already running"):
                await bus.run(dummy_callback)

            # Clean up
            await bus.stop()
            await run_task

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop twice should be safe - second call is no-op."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

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

        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            # Run run() in background since it blocks
            run_task = asyncio.create_task(bus.run(dummy_callback))
            await asyncio.sleep(0.1)

            await bus.stop()
            await run_task
            await bus.stop()  # Second call should be no-op

            # Should only stop once
            mock_app.stop.assert_called_once()

    @pytest.mark.anyio
    async def test_stop_without_run_is_safe(self):
        """Calling stop without run should be safe - no-op."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        # Should not raise
        await bus.stop()

    @pytest.mark.anyio
    async def test_can_rerun_after_stop(self):
        """Should be able to run again after stop."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

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

        async def dummy_callback(msg: str, ctx: TelegramContext) -> None:
            pass

        with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            # First cycle
            run_task = asyncio.create_task(bus.run(dummy_callback))
            await asyncio.sleep(0.1)
            await bus.stop()
            await run_task

            # Reset mock counts
            mock_app.initialize.reset_mock()

            # Second cycle should work
            run_task2 = asyncio.create_task(bus.run(dummy_callback))
            await asyncio.sleep(0.1)
            mock_app.initialize.assert_called_once()

            # Clean up
            await bus.stop()
            await run_task2
