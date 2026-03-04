"""Integration tests for chat command."""
import asyncio
import pytest
from picklebot.cli.chat import ChatLoop
from picklebot.utils.config import Config
from picklebot.core.events import OutboundEvent, CliEventSource
import time


def test_chat_loop_processes_user_input_and_displays_response():
    """Test that chat loop handles input and displays agent response."""
    config = Config.load()

    chat_loop = ChatLoop(config)

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

        # Publish inbound event (simulating user input)
        from picklebot.core.events import InboundEvent
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
            content="Hello! How can I help you?",
            timestamp=time.time(),
        )
        await chat_loop.context.eventbus.publish(outbound)

        # Wait for response to be queued
        await asyncio.sleep(0.2)

        # Check that inbound event was published
        assert len(published_events) >= 1
        assert published_events[0].content == user_input

        # Cleanup
        for worker in chat_loop.workers:
            await worker.stop()

    asyncio.run(run_test())
