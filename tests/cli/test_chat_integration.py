"""Integration test for CLI MessageBus flow through workers."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config, LLMConfig, MessageBusConfig, CliConfig


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
            enabled=True,
            default_platform="cli",
            cli=CliConfig(enabled=True),
        ),
    )


@pytest.mark.asyncio
async def test_cli_message_flow_through_workers(integration_config: Config):
    """
    Test complete message flow from stdin through MessageBusWorker and AgentDispatcherWorker.

    This integration test verifies:
    1. CliBus receives input from mocked stdin
    2. MessageBusWorker dispatches message to agent_queue
    3. AgentDispatcherWorker picks up the job
    4. SharedContext has agent_queue properly initialized
    """
    # Create CliBus
    bus = CliBus()

    # Create SharedContext with buses=[bus]
    context = SharedContext(config=integration_config, buses=[bus])

    # Verify context has agent_queue (lazy initialization)
    assert hasattr(context, "_agent_queue")
    assert context._agent_queue is None  # Not yet initialized

    # Create workers
    messagebus_worker = MessageBusWorker(context, agent_id="test-agent")
    dispatcher_worker = AgentDispatcherWorker(context)

    # Verify context now has agent_queue initialized via property access
    _ = context.agent_queue
    assert context._agent_queue is not None
    assert isinstance(context._agent_queue, asyncio.Queue)

    # Track if message was dispatched
    message_dispatched = asyncio.Event()
    original_put = context.agent_queue.put

    async def tracked_put(job):
        message_dispatched.set()
        return await original_put(job)

    # Patch the queue's put method to track dispatch
    context.agent_queue.put = tracked_put

    # Mock input to simulate user typing "test message" then "quit"
    with patch(
        "picklebot.messagebus.cli_bus.input", side_effect=["test message", "quit"]
    ):
        # Start both workers as background tasks
        bus_task = asyncio.create_task(messagebus_worker.run())
        dispatcher_task = asyncio.create_task(dispatcher_worker.run())

        try:
            # Wait for message to be dispatched (with timeout)
            await asyncio.wait_for(message_dispatched.wait(), timeout=2.0)

            # Verify a job was added to the queue
            assert not context.agent_queue.empty()

            # Get the job to verify its structure
            job = context.agent_queue.get_nowait()
            assert job.message == "test message"
            assert job.agent_id == "test-agent"

            # Wait a bit for bus to process quit command
            await asyncio.sleep(0.2)

        finally:
            # Cleanup: cancel workers
            bus_task.cancel()
            dispatcher_task.cancel()

            # Wait for tasks to finish
            try:
                await asyncio.wait_for(bus_task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

            try:
                await asyncio.wait_for(dispatcher_task, timeout=1.0)
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

    # Create MessageBusWorker
    worker = MessageBusWorker(context, agent_id="test-agent")

    # Verify worker has the bus from context
    assert len(worker.buses) == 1
    assert worker.buses[0] is bus
    assert worker.bus_map["cli"] is bus
