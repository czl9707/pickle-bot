"""Tests for MessageBusWorker."""

import asyncio
import pytest
from unittest.mock import patch
from dataclasses import dataclass

from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.server.base import Job
from picklebot.messagebus.base import MessageContext


@dataclass
class FakeContext(MessageContext):
    """Fake context with user_id for testing."""

    user_id: str
    chat_id: str


class FakeBus:
    """Fake MessageBus for testing."""

    def __init__(self):
        self.platform_name = "fake"
        self.messages: list[str] = []
        self.started = False

    async def run(self, callback):
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


class FakeBusWithUser(FakeBus):
    """Fake bus that provides user_id in context."""

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Simulate receiving a message with user context
        await callback("hello", FakeContext(user_id="123", chat_id="456"))


class FakeTelegramBus(FakeBus):
    """Fake bus that reports as telegram platform."""

    def __init__(self):
        super().__init__()
        self.platform_name = "telegram"

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Simulate receiving a message with user context
        await callback("hello", FakeContext(user_id="123", chat_id="456"))


class BlockingBusWithUser(FakeBusWithUser):
    """Fake bus that blocks all messages."""

    def is_allowed(self, context):
        return False


@pytest.mark.anyio
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
    bus = FakeBusWithUser()

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)
        # Patch _get_or_create_session_id to return a known session ID for testing
        worker._get_or_create_session_id = lambda platform, user_id: "test-session-123"

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
    assert job.session_id == "test-session-123"  # Session ID assigned per user


@pytest.mark.anyio
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
    bus = BlockingBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Queue should be empty - message was blocked
    assert queue.empty()


@pytest.mark.anyio
async def test_messagebus_worker_creates_per_user_session(test_context, tmp_path):
    """MessageBusWorker creates a new session for each user."""
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
    bus = FakeBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)

    # Should NOT have global_session anymore
    assert not hasattr(worker, "global_session")

    # Should have agent for session creation
    assert worker.agent is not None


@pytest.mark.anyio
async def test_messagebus_worker_reuses_existing_session(test_context, tmp_path):
    """MessageBusWorker reuses session from config for returning users."""
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

    # Pre-configure a session for user "123"
    from picklebot.utils.config import TelegramConfig, MessageBusConfig

    test_context.config.messagebus = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(
            bot_token="test", sessions={"123": "existing-session-uuid"}
        ),
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = FakeTelegramBus()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context, queue)

    # Start worker
    task = asyncio.create_task(worker.run())

    # Wait for message to be dispatched
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check queue has job with the existing session_id
    assert not queue.empty()
    job = await queue.get()
    assert job.session_id == "existing-session-uuid"
