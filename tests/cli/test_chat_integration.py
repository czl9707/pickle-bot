"""Integration test for CLI MessageBus flow through workers."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.core.events import Event, InboundEvent
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config, LLMConfig, MessageBusConfig


@pytest.fixture
def integration_config(tmp_path: Path) -> Config:
    """Config with CLI messagebus enabled for integration testing."""
    llm_config = LLMConfig(provider="openai", model="gpt-4", api_key="test-key")

    # Create agents directory with a test agent
    agents_dir = tmp_path / "agents" / "test-agent"
    agents_dir.mkdir(parents=True)

    # Create AGENT.md file (required format for agent_loader)
    agent_file = agents_dir / "AGENT.md"
    agent_file.write_text(
        """---
name: Test Agent
description: Integration test agent
---

You are a test assistant.
"""
    )

    return Config(
        workspace=tmp_path,
        llm=llm_config,
        default_agent="test-agent",
        agents_path=Path("agents"),
        messagebus=MessageBusConfig(
            enabled=False,  # CLI bypasses config anyway
        ),
        routing={
            "bindings": [
                {"agent": "test-agent", "value": "cli:.*"},
            ]
        },
    )


@pytest.mark.asyncio
async def test_cli_message_flow_through_workers(integration_config: Config):
    """
    Test complete message flow from stdin through MessageBusWorker publishing events.

    This integration test verifies:
    1. CliBus receives input from mocked stdin
    2. MessageBusWorker publishes INBOUND event to EventBus
    3. Event has correct type, source, content, and metadata
    """
    # Create CliBus
    bus = CliBus()

    # Create SharedContext with buses=[bus]
    context = SharedContext(config=integration_config, buses=[bus])

    # Verify context has eventbus
    assert hasattr(context, "eventbus")

    # Create workers (uses default agent from config)
    # AgentWorker auto-subscribes in __init__
    messagebus_worker = MessageBusWorker(context)
    AgentWorker(context)  # Creates worker that auto-subscribes to events

    # Track published events
    published_events: list[Event] = []

    async def capture_event(event: Event):
        published_events.append(event)

    context.eventbus.subscribe(InboundEvent, capture_event)

    # Mock input to simulate user typing "test message" then "quit"
    with patch(
        "picklebot.messagebus.cli_bus.input", side_effect=["test message", "quit"]
    ):
        # Start EventBus as worker (processes queued events)
        eventbus_task = context.eventbus.start()

        # Start MessageBusWorker as background task
        bus_task = asyncio.create_task(messagebus_worker.run())

        try:
            # Wait for event to be published (with timeout)
            await asyncio.wait_for(
                asyncio.sleep(0.5), timeout=2.0
            )  # Allow time for event processing

            # Verify an INBOUND event was published
            assert len(published_events) >= 1
            event = published_events[0]

            # Verify event structure
            assert isinstance(event, InboundEvent)
            assert event.content == "test message"
            assert str(event.source).startswith("platform-cli:")
            assert event.timestamp > 0

            # Wait a bit for bus to process quit command
            await asyncio.sleep(0.2)

        finally:
            # Cleanup: cancel workers
            bus_task.cancel()
            eventbus_task.cancel()

            # Wait for tasks to finish
            try:
                await asyncio.wait_for(bus_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

            try:
                await asyncio.wait_for(eventbus_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass


@pytest.mark.asyncio
async def test_shared_context_with_custom_buses(integration_config: Config):
    """
    Test that SharedContext properly accepts and use custom buses parameter.
    """
    # Create multiple buses
    bus1 = CliBus()
    bus2 = CliBus()

    # Create context with custom buses
    context = SharedContext(config=integration_config, buses=[bus1, bus2])

    # Verify buses are set correctly
    assert len(context.messagebus_buses) == 2
    assert context.messagebus_buses[0] is bus1
    assert context.messagebus_buses[1] is bus2


@pytest.mark.asyncio
async def test_messagebus_worker_uses_context_buses(integration_config: Config):
    """
    Test that MessageBusWorker uses buses from SharedContext.
    """
    # Create a bus
    bus = CliBus()

    # Create context with the bus
    context = SharedContext(config=integration_config, buses=[bus])

    # Create MessageBusWorker (uses default agent)
    worker = MessageBusWorker(context)

    # Verify worker has the bus from context
    assert len(worker.buses) == 1
    assert worker.buses[0] is bus
    assert worker.bus_map["cli"] is bus
