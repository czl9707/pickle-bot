"""Integration tests for chat command."""

import asyncio
import time

import pytest

from picklebot.cli.chat import ChatLoop
from picklebot.core.events import InboundEvent, OutboundEvent, CliEventSource
from picklebot.utils.config import Config


def test_chat_loop_processes_user_input_and_displays_response(test_config: Config):
    """Test that chat loop handles input and displays agent response."""
    chat_loop = ChatLoop(test_config)

    # Verify response_queue exists
    assert hasattr(
        chat_loop, "response_queue"
    ), "ChatLoop should have a response_queue attribute"

    # Track published events
    published_events = []
    original_publish = chat_loop.context.eventbus.publish

    async def track_publish(event):
        published_events.append(event)
        await original_publish(event)

    chat_loop.context.eventbus.publish = track_publish

    # Simulate chat interaction
    async def run_test():
        # Start workers
        for worker in chat_loop.workers:
            worker.start()

        # Give workers time to start
        await asyncio.sleep(0.1)

        # Simulate user input and agent response
        user_input = "Hello, agent!"
        expected_response = "Hello! How can I help you?"

        # Publish inbound event (simulating user input)
        inbound = InboundEvent(
            session_id="test-session",
            agent_id="default",
            source=CliEventSource(),
            content=user_input,
            timestamp=time.time(),
        )
        await chat_loop.context.eventbus.publish(inbound)

        # Simulate agent response
        outbound = OutboundEvent(
            session_id="test-session",
            agent_id="default",
            source=CliEventSource(),
            content=expected_response,
            timestamp=time.time(),
        )
        await chat_loop.context.eventbus.publish(outbound)

        # Wait for response to be queued
        await asyncio.sleep(0.2)

        # Check that inbound event was published
        assert len(published_events) >= 1
        assert published_events[0].content == user_input

        # Verify response queue mechanism
        assert (
            not chat_loop.response_queue.empty()
        ), "Response should be queued in response_queue"

        # Get the queued response and verify its content
        queued_response = chat_loop.response_queue.get_nowait()
        assert (
            queued_response.content == expected_response
        ), "Queued response should match agent output"

        # Cleanup
        for worker in chat_loop.workers:
            await worker.stop()

    asyncio.run(run_test())


def test_chat_loop_has_no_messagebus_worker(test_config: Config):
    """Test that ChatLoop doesn't use MessageBusWorker."""
    chat_loop = ChatLoop(test_config)

    # Check workers list
    worker_types = [type(worker).__name__ for worker in chat_loop.workers]

    # Should have EventBus, AgentWorker, but NOT MessageBusWorker or DeliveryWorker
    assert "EventBus" in worker_types
    assert "AgentWorker" in worker_types
    assert "MessageBusWorker" not in worker_types
    assert "DeliveryWorker" not in worker_types


def test_warnings_are_suppressed():
    """Test that Python warnings are suppressed during chat."""
    import warnings

    # Import chat module (triggers suppression)
    import picklebot.cli.chat  # noqa: F401

    # Check that an "ignore" filter is set at the module level
    # The filters list contains tuples of (action, message, category, module, lineno)
    filters = warnings.filters

    # Check that there's an "ignore" filter that applies to all warnings
    # Filter tuple structure: (action, message, category, module, lineno)
    has_ignore_filter = any(f[0] == "ignore" for f in filters)
    assert has_ignore_filter, "chat.py should set warnings.filterwarnings('ignore')"


@pytest.mark.asyncio
async def test_chat_loop_subscribes_to_outbound_events(test_config: Config):
    """Test that ChatLoop subscribes to OutboundEvents."""
    chat_loop = ChatLoop(test_config)

    # Check subscription exists
    subscribers = chat_loop.context.eventbus._subscribers.get(OutboundEvent, [])
    assert len(subscribers) > 0
    assert chat_loop.handle_outbound_event in subscribers


def test_get_user_input_returns_trimmed_input(test_config: Config):
    """Test that get_user_input returns trimmed user input."""
    import io
    import sys

    chat_loop = ChatLoop(test_config)

    # Mock stdin with input that has leading/trailing whitespace
    test_input = "  Hello, agent!  \n"
    sys.stdin = io.StringIO(test_input)

    result = chat_loop.get_user_input()

    assert result == "Hello, agent!"

    # Restore stdin
    sys.stdin = sys.__stdin__


def test_display_agent_response_prints_styled_output(test_config: Config):
    """Test that display_agent_response prints with green prefix."""
    from io import StringIO

    chat_loop = ChatLoop(test_config)

    # Capture stdout
    captured_output = StringIO()
    import sys

    sys.stdout = captured_output

    chat_loop.display_agent_response("Hello! How can I help you?")

    output = captured_output.getvalue()
    sys.stdout = sys.__stdout__

    # Check that output contains the response
    assert "Hello! How can I help you?" in output


@pytest.mark.asyncio
async def test_chat_loop_handles_quit_command(test_config: Config):
    """Test that chat loop exits on quit command."""
    import io
    import sys

    chat_loop = ChatLoop(test_config)

    # Mock input to return 'quit'
    sys.stdin = io.StringIO("quit\n")

    # Start workers
    for worker in chat_loop.workers:
        worker.start()

    # Run chat loop (should exit quickly)
    try:
        await asyncio.wait_for(chat_loop.run(), timeout=1.0)
    except asyncio.TimeoutError:
        # If it times out, quit didn't work
        assert False, "Chat loop didn't exit on quit command"
    finally:
        sys.stdin = sys.__stdin__
        for worker in chat_loop.workers:
            await worker.stop()
