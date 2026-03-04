"""Integration tests for chat command."""

import asyncio
import time

from picklebot.cli.chat import ChatLoop
from picklebot.core.events import InboundEvent, OutboundEvent
from picklebot.messagebus.cli_bus import CliEventSource
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
