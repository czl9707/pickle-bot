"""End-to-end tests for command dispatch flow."""

import asyncio

import pytest

from tests.helpers import create_test_agent

from picklebot.core.events import InboundEvent, OutboundEvent, CliEventSource
from picklebot.server.agent_worker import AgentWorker


async def test_clear_command_flow(test_context, tmp_path):
    """Test /clear command clears conversation."""
    create_test_agent(tmp_path, agent_id="pickle", name="Pickle")

    # Setup worker
    worker = AgentWorker(test_context)

    # Track outbound events
    outbound_events: list[OutboundEvent] = []

    async def capture_outbound(evt: OutboundEvent) -> None:
        outbound_events.append(evt)

    test_context.eventbus.subscribe(OutboundEvent, capture_outbound)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        # Message 1: Some conversation
        pickle_def = test_context.agent_loader.load("pickle")
        event1 = InboundEvent(
            session_id="session-1",
            source=CliEventSource(),
            content="Hello",
            timestamp=1000.0,
        )
        await worker.exec_session(event1, pickle_def)

        # Wait for event processing
        await asyncio.sleep(0.1)

        # Add session to cache
        source_str = "platform-cli:cli-user"
        test_context.config.sources[source_str] = {"session_id": "session-1"}

        # Message 2: Clear command
        event2 = InboundEvent(
            session_id="session-1",
            source=CliEventSource(),
            content="/clear",
            timestamp=1001.0,
        )
        await worker.exec_session(event2, pickle_def)

        # Wait for event processing
        await asyncio.sleep(0.1)

        # Verify cache cleared
        assert source_str not in test_context.config.sources

    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass
