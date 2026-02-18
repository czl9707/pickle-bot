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

    with patch("picklebot.messagebus.telegram_bus.Application.builder") as mock_builder:
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
async def test_telegram_bus_send_message_not_started():
    """Test that send_message raises when not started."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)

    with pytest.raises(RuntimeError, match="TelegramBus not started"):
        await bus.send_message(content="Hello, world!", user_id="12345")


class TestTelegramBusSendMesssageUserIdHandling:
    """Tests for send_message user_id handling."""

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "user_id,default_user_id,expected_chat_id,should_raise",
        [
            # Explicit user_id overrides default
            ("111222333", "999888777", 111222333, False),
            # Fallback to default when no user_id
            (None, "999888777", 999888777, False),
            # Error when neither provided
            (None, None, None, True),
        ],
        ids=["explicit_user_id", "fallback_to_default", "error_no_user_no_default"],
    )
    async def test_send_message_user_id_handling(
        self, user_id, default_user_id, expected_chat_id, should_raise
    ):
        """Test send_message handles user_id correctly in all cases."""
        config = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            default_user_id=default_user_id,
        )
        bus = TelegramBus(config)

        # Mock the application
        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        if should_raise:
            with pytest.raises(
                ValueError, match="No user_id provided and no default_user_id configured"
            ):
                await bus.send_message(content="Test message", user_id=user_id)
        else:
            await bus.send_message(content="Test message", user_id=user_id)

            mock_app.bot.send_message.assert_called_once()
            call_args = mock_app.bot.send_message.call_args
            assert call_args.kwargs["chat_id"] == expected_chat_id
            assert call_args.kwargs["text"] == "Test message"
