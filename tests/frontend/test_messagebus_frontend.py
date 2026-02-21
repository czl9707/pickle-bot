"""Tests for MessageBusFrontend."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from picklebot.frontend.messagebus import MessageBusFrontend
from picklebot.messagebus.telegram_bus import TelegramContext


class TestMessageBusFrontend:
    """Tests for MessageBusFrontend class."""

    @pytest.fixture
    def mock_bus(self):
        """Create a mock MessageBus."""
        bus = MagicMock()
        bus.reply = AsyncMock()
        return bus

    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        return TelegramContext(user_id="123", chat_id="456")

    @pytest.fixture
    def frontend(self, mock_bus, mock_context):
        """Create a MessageBusFrontend instance."""
        return MessageBusFrontend(mock_bus, mock_context)

    @pytest.mark.anyio
    async def test_show_message_sends_via_bus(self, frontend, mock_bus, mock_context):
        """show_message should call bus.reply with content."""
        await frontend.show_message("Hello world")

        mock_bus.reply.assert_called_once_with("Hello world", mock_context)

    @pytest.mark.anyio
    async def test_show_message_with_agent_id_prefixes_content(
        self, frontend, mock_bus, mock_context
    ):
        """show_message should prefix with agent_id when provided."""
        await frontend.show_message("Hello", agent_id="pickle")

        mock_bus.reply.assert_called_once_with("[pickle]: Hello", mock_context)

    @pytest.mark.anyio
    async def test_show_system_message_sends_via_bus(
        self, frontend, mock_bus, mock_context
    ):
        """show_system_message should call bus.reply with content."""
        await frontend.show_system_message("Goodbye!")

        mock_bus.reply.assert_called_once_with("Goodbye!", mock_context)

    @pytest.mark.anyio
    async def test_show_dispatch_sends_notification(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch context manager should send notification on enter."""
        async with frontend.show_dispatch("Pickle", "Cookie", "Remember this"):
            pass

        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args
        assert call_args[0][0] == "Pickle: @cookie Remember this"
        assert call_args[0][1] == mock_context

    @pytest.mark.anyio
    async def test_show_dispatch_lowercases_target(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch should lowercase target agent name."""
        async with frontend.show_dispatch("Agent", "MySubAgent", "Do task"):
            pass

        call_args = mock_bus.reply.call_args
        message = call_args[0][0]
        assert "@mysubagent" in message.lower()

    @pytest.mark.anyio
    async def test_show_message_error_isolation(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """show_message should catch exceptions and log warnings, not raise."""
        mock_bus.reply.side_effect = Exception("Network error")

        with caplog.at_level(logging.WARNING):
            await frontend.show_message("test message")

        assert any(
            "Failed to send message" in record.message for record in caplog.records
        )
        assert any("Network error" in record.message for record in caplog.records)

    @pytest.mark.anyio
    async def test_show_dispatch_error_isolation(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """show_dispatch should catch exceptions and log warnings, not raise."""
        mock_bus.reply.side_effect = Exception("API error")

        with caplog.at_level(logging.WARNING):
            async with frontend.show_dispatch("Pickle", "Cookie", "task"):
                pass

        assert any(
            "Failed to send dispatch notification" in record.message
            for record in caplog.records
        )
