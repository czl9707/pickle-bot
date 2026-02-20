"""Tests for MessageBusFrontend."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.frontend.messagebus_frontend import MessageBusFrontend
from picklebot.messagebus.base import TelegramContext


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

    def test_show_welcome_is_noop(self, frontend):
        """show_welcome should be a no-op."""
        frontend.show_welcome()  # Should not raise

    def test_show_message_is_noop(self, frontend):
        """show_message should be a no-op."""
        frontend.show_message("test content")  # Should not raise

    def test_show_system_message_is_noop(self, frontend):
        """show_system_message should be a no-op."""
        frontend.show_system_message("system message")  # Should not raise

    def test_show_transient_is_noop(self, frontend):
        """show_transient should be a no-op context manager."""
        with frontend.show_transient("loading..."):
            pass  # Should not raise

    @pytest.mark.anyio
    async def test_show_dispatch_start_creates_task(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch_start should create async task with correct message."""
        frontend.show_dispatch_start("Pickle", "Cookie", "Remember this")

        # Give the task a moment to run
        await asyncio.sleep(0.1)

        # Verify reply was called with formatted message
        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args
        assert call_args[0][0] == "Pickle: @cookie Remember this"
        assert call_args[0][1] == mock_context

    @pytest.mark.anyio
    async def test_show_dispatch_start_lowercase_target(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch_start should lowercase target agent name."""
        frontend.show_dispatch_start("Agent", "MySubAgent", "Do task")

        # Give the task a moment to run
        await asyncio.sleep(0.1)

        # Verify target agent is lowercased
        call_args = mock_bus.reply.call_args
        message = call_args[0][0]
        assert "@mysubagent" in message.lower()

    @pytest.mark.anyio
    async def test_show_dispatch_result_truncates_long_results(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch_result should truncate results longer than 200 chars."""
        long_result = "x" * 300  # 300 chars

        frontend.show_dispatch_result("Pickle", "Cookie", long_result)

        # Give the task a moment to run
        await asyncio.sleep(0.1)

        # Verify reply was called with truncated message
        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args
        message = call_args[0][0]

        # Should contain truncated result (200 chars + "...")
        assert "xxx..." in message
        assert len(message) < 250  # message + prefix should be short

    @pytest.mark.anyio
    async def test_show_dispatch_result_keeps_short_results(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch_result should not truncate results 200 chars or less."""
        short_result = "Task completed successfully"

        frontend.show_dispatch_result("Pickle", "Cookie", short_result)

        # Give the task a moment to run
        await asyncio.sleep(0.1)

        # Verify reply was called with full message
        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args
        message = call_args[0][0]

        # Should contain full result without truncation
        assert short_result in message
        assert "..." not in message

    @pytest.mark.anyio
    async def test_show_dispatch_result_formats_correctly(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch_result should format message as 'Agent: - result'."""
        result = "Done"

        frontend.show_dispatch_result("Caller", "Target", result)

        # Give the task a moment to run
        await asyncio.sleep(0.1)

        call_args = mock_bus.reply.call_args
        message = call_args[0][0]

        assert message == "Target: - Done"

    @pytest.mark.anyio
    async def test_error_handling_when_reply_fails(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """_post_safe should catch exceptions and log warnings, not raise."""
        # Make reply raise an exception
        mock_bus.reply.side_effect = Exception("Network error")

        # This should not raise, just log a warning
        with caplog.at_level(logging.WARNING):
            await frontend._post_safe("test message")

        # Verify warning was logged
        assert any(
            "Failed to post message" in record.message for record in caplog.records
        )
        assert any("Network error" in record.message for record in caplog.records)

    @pytest.mark.anyio
    async def test_show_dispatch_start_continues_on_error(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """show_dispatch_start should continue execution even if reply fails."""
        # Make reply raise an exception
        mock_bus.reply.side_effect = Exception("API error")

        with caplog.at_level(logging.WARNING):
            frontend.show_dispatch_start("Pickle", "Cookie", "task")

            # Give the task time to complete
            await asyncio.sleep(0.2)

        # Should have logged warning, not raised
        assert any(
            "Failed to post message" in record.message for record in caplog.records
        )

    @pytest.mark.anyio
    async def test_show_dispatch_result_continues_on_error(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """show_dispatch_result should continue execution even if reply fails."""
        # Make reply raise an exception
        mock_bus.reply.side_effect = Exception("API error")

        with caplog.at_level(logging.WARNING):
            frontend.show_dispatch_result("Pickle", "Cookie", "result")

            # Give the task time to complete
            await asyncio.sleep(0.2)

        # Should have logged warning, not raised
        assert any(
            "Failed to post message" in record.message for record in caplog.records
        )
