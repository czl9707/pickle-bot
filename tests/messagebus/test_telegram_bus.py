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
    await bus.send_message(content="Hello, world!", user_id="12345")

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
        await bus.send_message(content="Hello, world!", user_id="12345")


class TestTelegramBusDefaultUser:
    """Tests for default user ID fallback."""

    def test_send_message_uses_default_user_when_not_provided(self):
        """send_message should use default_user_id when user_id is None."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="123456789",
        )
        bus = TelegramBus(config)

        # Verify config has the default
        assert bus.config.default_user_id == "123456789"

    @pytest.mark.anyio
    async def test_send_message_falls_back_to_default(self):
        """When user_id is None, should send to default_user_id."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="999888777",
        )
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        # Call without user_id
        await bus.send_message(content="Test message")

        # Should have called with default user_id
        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 999888777
        assert call_args.kwargs["text"] == "Test message"

    @pytest.mark.anyio
    async def test_send_message_with_explicit_user_id(self):
        """When user_id is provided, should use it instead of default."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id="999888777",
        )
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        # Call with explicit user_id
        await bus.send_message(content="Test message", user_id="111222333")

        # Should have called with explicit user_id, not default
        mock_app.bot.send_message.assert_called_once()
        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 111222333
        assert call_args.kwargs["text"] == "Test message"

    @pytest.mark.anyio
    async def test_send_message_no_user_no_default_raises(self):
        """Should raise ValueError when no user_id and no default configured."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id=None,  # No default configured
        )
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        # Should raise ValueError
        with pytest.raises(ValueError, match="No user_id provided and no default_user_id configured"):
            await bus.send_message(content="Test message")
