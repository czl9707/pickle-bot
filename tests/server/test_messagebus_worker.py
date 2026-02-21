"""Tests for MessageBusWorker."""

import asyncio
import pytest

from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.server.base import Job


class FakeBus:
    """Fake MessageBus for testing."""

    def __init__(self):
        self.platform_name = "fake"
        self.messages: list[str] = []
        self.started = False

    async def start(self, callback):
        self.started = True
        self._callback = callback
        # Simulate receiving a message
        await callback("hello", {"chat_id": "123"})

    async def stop(self):
        self.started = False

    def is_allowed(self, context):
        return True

    async def reply(self, content, context):
        self.messages.append(content)


class BlockingBus(FakeBus):
    """Fake bus that blocks all messages."""

    def is_allowed(self, context):
        return False


@pytest.mark.asyncio
async def test_messagebus_worker_creates_global_session(test_context, tmp_path):
    """MessageBusWorker creates a global session on init."""
    # Create test agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    bus = FakeBus()
    worker = MessageBusWorker(test_context, asyncio.Queue(), [bus])

    assert worker.global_session is not None
    assert worker.global_session.agent_id == "test"


@pytest.mark.asyncio
async def test_messagebus_worker_dispatches_to_queue(test_context, tmp_path):
    """MessageBusWorker dispatches incoming messages to agent queue."""
    # Create test agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = FakeBus()
    worker = MessageBusWorker(test_context, queue, [bus])

    # Start worker (it will process one message and wait)
    task = asyncio.create_task(worker.run())

    # Wait for message to be dispatched
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check queue has job
    assert not queue.empty()
    job = await queue.get()
    assert job.message == "hello"
    assert job.session_id == worker.global_session.session_id


@pytest.mark.asyncio
async def test_messagebus_worker_ignores_non_whitelisted(test_context, tmp_path):
    """MessageBusWorker ignores messages from non-whitelisted senders."""
    # Create test agent
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---

You are a test assistant.
"""
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = BlockingBus()
    worker = MessageBusWorker(test_context, queue, [bus])

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Queue should be empty - message was blocked
    assert queue.empty()
