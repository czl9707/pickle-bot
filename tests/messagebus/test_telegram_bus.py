"""Tests for TelegramBus."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.utils.config import TelegramConfig


def test_telegram_bus_platform_name():
    """Test that TelegramBus has correct platform name."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)
    assert bus.platform_name == "telegram"


@pytest.mark.anyio
async def test_telegram_bus_start_stop():
    """Test that TelegramBus can start and stop."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)

    # Mock the Application
    mock_app = MagicMock()
    mock_app.updater = MagicMock()
    mock_app.updater.running = True  # Simulate running state after start
    mock_app.updater.start_polling = AsyncMock()
    mock_app.updater.stop = AsyncMock()
    mock_app.initialize = AsyncMock()
    mock_app.start = AsyncMock()
    mock_app.stop = AsyncMock()
    mock_app.shutdown = AsyncMock()
    mock_app.add_handler = MagicMock()
    mock_app.bot = MagicMock()

    with patch(
        "picklebot.messagebus.telegram_bus.Application.builder"
    ) as mock_builder:
        mock_builder.return_value.token.return_value.build.return_value = mock_app

        # Should not raise
        await bus.start(lambda msg, plat, uid: None)
        await bus.stop()

        # Verify lifecycle was called
        mock_app.initialize.assert_called_once()
        mock_app.start.assert_called_once()
        mock_app.updater.start_polling.assert_called_once()
        mock_app.updater.stop.assert_called_once()
        mock_app.stop.assert_called_once()
        mock_app.shutdown.assert_called_once()


@pytest.mark.anyio
async def test_telegram_bus_send_message():
    """Test that TelegramBus can send messages."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)

    # Mock the Application
    mock_app = MagicMock()
    mock_app.bot = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    # Set the application directly (simulating started state)
    bus.application = mock_app

    # Send a message
    await bus.send_message("12345", "Hello, world!")

    # Verify the message was sent
    mock_app.bot.send_message.assert_called_once_with(
        chat_id=12345, text="Hello, world!"
    )


@pytest.mark.anyio
async def test_telegram_bus_send_message_not_started():
    """Test that send_message raises when not started."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)

    with pytest.raises(RuntimeError, match="TelegramBus not started"):
        await bus.send_message("12345", "Hello, world!")
