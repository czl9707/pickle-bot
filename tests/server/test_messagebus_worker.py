"""Tests for MessageBusWorker."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from dataclasses import dataclass

from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.messagebus.base import MessageContext
from picklebot.core.commands import CommandRegistry
from picklebot.core.context import SharedContext


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

    bus = FakeBusWithUser()

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
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

    # Check queue has job (via context.agent_queue)
    queue = test_context.agent_queue
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

    bus = BlockingBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Queue should be empty - message was blocked
    queue = test_context.agent_queue
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

    bus = FakeBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)

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

    bus = FakeTelegramBus()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)  # No queue param

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
    queue = test_context.agent_queue
    assert not queue.empty()
    job = await queue.get()
    assert job.session_id == "existing-session-uuid"


@pytest.mark.anyio
async def test_messagebus_worker_uses_context_queue(test_context, tmp_path):
    """MessageBusWorker should get queue from context."""
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

    bus = FakeBusWithUser()
    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda platform, user_id: "test-session-123"

    # Worker should use context's queue
    assert worker.context.agent_queue is test_context.agent_queue

    # Verify it dispatches to the context queue
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Job should be in context's queue
    queue = test_context.agent_queue
    assert not queue.empty()
    job = await queue.get()
    assert job.message == "hello"


class TestMessageBusWorkerSlashCommands:
    """Tests for slash command handling in MessageBusWorker."""

    @pytest.fixture
    def mock_context(self, test_config, test_agent_def):
        """Create mock context with minimal setup."""
        context = MagicMock(spec=SharedContext)
        context.config = test_config
        context.agent_loader = MagicMock()
        context.agent_loader.load.return_value = test_agent_def
        context.config.messagebus = MagicMock()
        context.config.messagebus.telegram = None
        context.config.messagebus.discord = None
        context.command_registry = CommandRegistry.with_builtins()
        return context

    def test_context_has_command_registry(self, mock_context):
        """SharedContext should have CommandRegistry."""
        mock_context.messagebus_buses = []

        MessageBusWorker(mock_context)

        assert mock_context.command_registry is not None
        assert isinstance(mock_context.command_registry, CommandRegistry)

    @pytest.mark.anyio
    async def test_callback_handles_slash_command(self, mock_context):
        """Callback should dispatch slash commands and reply directly."""
        mock_context.messagebus_buses = []
        mock_context.agent_queue = AsyncMock()

        worker = MessageBusWorker(mock_context)

        # Create mock bus and context
        mock_bus = MagicMock()
        mock_bus.platform_name = "test"
        mock_bus.is_allowed.return_value = True
        mock_bus.reply = AsyncMock()

        mock_msg_context = MagicMock()
        mock_msg_context.user_id = "user123"

        # Add bus to bus_map
        worker.bus_map["test"] = mock_bus

        # Get the callback
        callback = worker._create_callback("test")

        # Send slash command
        await callback("/help", mock_msg_context)

        # Should have replied directly
        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args[0][0]
        assert "Available Commands" in call_args

        # Should NOT have put job in queue
        mock_context.agent_queue.put.assert_not_called()
