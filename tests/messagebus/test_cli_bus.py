"""Tests for CliBus implementation."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from picklebot.messagebus.cli_bus import CliBus, CliContext


class TestCliContext:
    """Tests for CliContext."""

    def test_cli_context_has_user_id(self):
        """CliContext should have user_id field."""
        ctx = CliContext()
        assert ctx.user_id == "cli-user"

    def test_cli_context_is_dataclass(self):
        """CliContext should be a dataclass."""
        ctx1 = CliContext()
        ctx2 = CliContext()
        assert ctx1 == ctx2  # Dataclass equality


class TestCliBusProperties:
    """Tests for CliBus basic properties."""

    def test_platform_name(self):
        """CliBus should have platform_name='cli'."""
        bus = CliBus()
        assert bus.platform_name == "cli"

    def test_is_allowed_always_true(self):
        """CliBus.is_allowed should always return True."""
        bus = CliBus()
        ctx = CliContext()
        assert bus.is_allowed(ctx) is True


class TestCliBusReplyAndPost:
    """Tests for CliBus reply() and post() methods."""

    def test_reply_prints_to_stdout(self, capsys):
        """reply() should print content to stdout via Rich Console."""
        bus = CliBus()
        ctx = CliContext()

        # Run async function
        asyncio.run(bus.reply("Hello, CLI!", ctx))

        # Check stdout contains the message
        captured = capsys.readouterr()
        assert "Hello, CLI!" in captured.out

    def test_post_prints_to_stdout(self, capsys):
        """post() should print content to stdout via Rich Console."""
        bus = CliBus()

        # Run async function
        asyncio.run(bus.post("Broadcast message"))

        # Check stdout contains the message
        captured = capsys.readouterr()
        assert "Broadcast message" in captured.out

    def test_post_ignores_target_parameter(self, capsys):
        """post() should ignore target parameter (CLI has no channels)."""
        bus = CliBus()

        # Run async function with target (should be ignored)
        asyncio.run(bus.post("Message", target="user:123"))

        # Check stdout contains the message
        captured = capsys.readouterr()
        assert "Message" in captured.out


class TestCliBusRun:
    """Tests for CliBus run() method."""

    @pytest.mark.asyncio
    async def test_run_calls_on_message_with_input(self):
        """run() should call on_message callback with user input."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to return a message then "quit"
        with patch("picklebot.messagebus.cli_bus.input", side_effect=["Hello", "quit"]):
            # Run in background task
            task = asyncio.create_task(bus.run(on_message))

            # Wait for message to be processed
            await asyncio.sleep(0.1)

            # Stop the bus
            await bus.stop()

            # Wait for task to complete
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.CancelledError:
                pass

        # Verify on_message was called with correct args
        assert on_message.called
        call_args = on_message.call_args
        message, context = call_args[0]
        assert message == "Hello"
        assert isinstance(context, CliContext)
        assert context.user_id == "cli-user"

    @pytest.mark.asyncio
    async def test_run_handles_quit_command(self):
        """run() should exit when user types 'quit'."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to return "quit" immediately
        with patch("picklebot.messagebus.cli_bus.input", return_value="quit"):
            # Run should complete without hanging
            await bus.run(on_message)

        # on_message should not be called for quit
        on_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_handles_exit_command(self):
        """run() should exit when user types 'exit'."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to return "exit" immediately
        with patch("picklebot.messagebus.cli_bus.input", return_value="exit"):
            await bus.run(on_message)

        # on_message should not be called for exit
        on_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_handles_q_command(self):
        """run() should exit when user types 'q'."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to return "q" immediately
        with patch("picklebot.messagebus.cli_bus.input", return_value="q"):
            await bus.run(on_message)

        # on_message should not be called for q
        on_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_skips_empty_input(self):
        """run() should skip empty or whitespace-only input."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to return empty strings and whitespace, then quit
        with patch(
            "picklebot.messagebus.cli_bus.input", side_effect=["", "   ", "\t", "quit"]
        ):
            await bus.run(on_message)

        # on_message should not be called for empty input
        on_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_handles_multiple_messages(self):
        """run() should handle multiple messages before quit."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to return multiple messages then quit
        with patch(
            "picklebot.messagebus.cli_bus.input", side_effect=["msg1", "msg2", "quit"]
        ):
            await bus.run(on_message)

        # on_message should be called twice
        assert on_message.call_count == 2

        # Check first call
        first_call = on_message.call_args_list[0]
        assert first_call[0][0] == "msg1"

        # Check second call
        second_call = on_message.call_args_list[1]
        assert second_call[0][0] == "msg2"

    @pytest.mark.asyncio
    async def test_run_raises_error_when_already_running(self):
        """run() should raise RuntimeError if called when already running."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to hang (never returns quit)
        input_called = asyncio.Event()

        def hanging_input():
            input_called.set()
            # Sleep for a long time
            import time

            time.sleep(10)
            return "quit"

        with patch("picklebot.messagebus.cli_bus.input", side_effect=hanging_input):
            # Start run in background
            task = asyncio.create_task(bus.run(on_message))

            # Wait for input to be called
            await asyncio.wait_for(input_called.wait(), timeout=1.0)

            # Give a bit more time for the _running flag to be set
            await asyncio.sleep(0.05)

            # Try to call run again - should raise RuntimeError
            with pytest.raises(RuntimeError, match="already running"):
                await bus.run(on_message)

            # Clean up
            await bus.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    @pytest.mark.asyncio
    async def test_run_case_insensitive_quit(self):
        """run() should handle quit commands case-insensitively."""
        bus = CliBus()
        on_message = AsyncMock()

        # Test QUIT (uppercase)
        with patch("picklebot.messagebus.cli_bus.input", return_value="QUIT"):
            await bus.run(on_message)

        on_message.assert_not_called()

        # Test Exit (mixed case)
        bus2 = CliBus()
        on_message2 = AsyncMock()
        with patch("picklebot.messagebus.cli_bus.input", return_value="Exit"):
            await bus2.run(on_message2)

        on_message2.assert_not_called()


class TestCliBusStop:
    """Tests for CliBus stop() method."""

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        """stop() should be safe to call multiple times."""
        bus = CliBus()

        # Should not raise any errors
        await bus.stop()
        await bus.stop()
        await bus.stop()

    @pytest.mark.asyncio
    async def test_stop_allows_restart(self):
        """stop() should allow run() to be called again."""
        bus = CliBus()
        on_message = AsyncMock()

        # Run and stop
        with patch("picklebot.messagebus.cli_bus.input", return_value="quit"):
            await bus.run(on_message)

        await bus.stop()

        # Should be able to run again
        with patch("picklebot.messagebus.cli_bus.input", return_value="quit"):
            await bus.run(on_message)

    @pytest.mark.asyncio
    async def test_stop_interrupts_running_bus(self):
        """stop() should interrupt a running bus."""
        bus = CliBus()
        on_message = AsyncMock()

        # Mock input to hang indefinitely
        def hanging_input():
            import time

            time.sleep(10)
            return "quit"

        with patch("picklebot.messagebus.cli_bus.input", side_effect=hanging_input):
            task = asyncio.create_task(bus.run(on_message))

            # Wait a bit for task to start
            await asyncio.sleep(0.1)

            # Stop should interrupt
            await bus.stop()

            # Task should complete quickly (not wait for 10 second sleep)
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

            # Task should be done
            assert task.done()
