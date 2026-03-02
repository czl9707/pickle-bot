"""Tests for TelegramBus."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from picklebot.messagebus.telegram_bus import TelegramBus, TelegramContext
from picklebot.utils.config import TelegramConfig


def test_telegram_bus_platform_name():
    """Test that TelegramBus has correct platform name."""
    config = TelegramConfig(bot_token="test_token")
    bus = TelegramBus(config)
    assert bus.platform_name == "telegram"


class TestTelegramBusReply:
    """Tests for TelegramBus.reply method."""

    @pytest.mark.anyio
    async def test_reply_raises_when_not_started(self):
        """reply should raise when not started."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        ctx = TelegramContext(user_id="user123", chat_id="456789")
        with pytest.raises(RuntimeError, match="TelegramBus not started"):
            await bus.reply(content="Hello, world!", context=ctx)

    @pytest.mark.anyio
    async def test_reply_sends_to_chat_id(self):
        """reply should send to context.chat_id."""
        config = TelegramConfig(bot_token="test-token")
        bus = TelegramBus(config)

        mock_app = MagicMock()
        mock_app.bot.send_message = AsyncMock()
        bus.application = mock_app

        ctx = TelegramContext(user_id="user123", chat_id="456789")
        await bus.reply(content="Test reply", context=ctx)

        call_args = mock_app.bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 456789
        assert call_args.kwargs["text"] == "Test reply"


class TestTelegramBusPost:
    """Tests for TelegramBus.post method."""

    @pytest.mark.anyio
    async def test_post_raises_when_not_started(self):
        """post should raise when not started."""
        config = TelegramConfig(bot_token="test_token")
        bus = TelegramBus(config)

        with pytest.raises(RuntimeError, match="TelegramBus not started"):
            await bus.post(content="Hello, world!")

    @pytest.mark.anyio
    async def test_post_raises_requires_target(self):
        """post should raise indicating it requires a target parameter."""
        config = TelegramConfig(bot_token="test-token")
        bus = TelegramBus(config)
        bus.application = MagicMock()

        with pytest.raises(ValueError, match="requires a target parameter"):
            await bus.post(content="Test")
