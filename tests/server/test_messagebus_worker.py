"""Tests for MessageBusWorker."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from dataclasses import dataclass

from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.messagebus.base import MessageContext
from picklebot.core.commands import CommandRegistry
from picklebot.core.context import SharedContext
from picklebot.core.events import InboundEvent, EventType


@dataclass
class FakeContext(MessageContext):
    """Fake context with user_id for testing."""

    user_id: str
    chat_id: str


@dataclass
class FakeDiscordContext(MessageContext):
    """Fake context for Discord testing."""

    user_id: str
    channel_id: str


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


class FakeDiscordBus(FakeBus):
    """Fake bus that reports as discord platform."""

    def __init__(self):
        super().__init__()
        self.platform_name = "discord"

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Simulate receiving a message with user context
        await callback("hello", FakeDiscordContext(user_id="456", channel_id="789"))


class BlockingBusWithUser(FakeBusWithUser):
    """Fake bus that blocks all messages."""

    def is_allowed(self, context):
        return False


@pytest.mark.anyio
async def test_messagebus_worker_publishes_inbound_event(test_context, tmp_path):
    """MessageBusWorker publishes INBOUND events to EventBus."""
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
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        # Patch _get_or_create_session_id to return a known session ID for testing
        worker._get_or_create_session_id = lambda platform, user_id: "test-session-123"
        # Subscribe to capture events
        test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        # Start worker (it will process one message and wait)
        task = asyncio.create_task(worker.run())

        # Wait for message to be dispatched
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify event was published
        assert len(published_events) == 1
        event = published_events[0]
        assert event.type == EventType.INBOUND
        assert event.content == "hello"
        assert event.session_id == "test-session-123"
        assert event.source == "fake:123"
        # InboundEvent has context field directly (not metadata)
        assert isinstance(event, InboundEvent)
        assert event.context is not None
        assert event.context.chat_id == "456"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


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
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # No event should have been published - message was blocked
    assert len(published_events) == 0


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
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        # Start worker
        task = asyncio.create_task(worker.run())

        # Wait for message to be dispatched
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify event has the existing session_id
        assert len(published_events) == 1
        event = published_events[0]
        assert event.session_id == "existing-session-uuid"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


@pytest.mark.anyio
async def test_messagebus_worker_includes_metadata(test_context, tmp_path):
    """MessageBusWorker includes platform-specific metadata in events."""
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

    bus = FakeDiscordBus()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda platform, user_id: "test-session-123"
        test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        # Start worker
        task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify event has Discord metadata (channel_id, not chat_id)
        assert len(published_events) == 1
        event = published_events[0]
        assert event.source == "discord:456"
        # InboundEvent has context field directly (not metadata)
        assert isinstance(event, InboundEvent)
        assert event.context is not None
        assert event.context.channel_id == "789"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


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
        # Add eventbus mock
        context.eventbus = MagicMock()
        context.eventbus.publish = AsyncMock()
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

        # Should NOT have published an event
        mock_context.eventbus.publish.assert_not_called()


@pytest.mark.anyio
async def test_messagebus_worker_uses_default_agent(test_context, tmp_path):
    """MessageBusWorker uses default agent from config."""
    # Create test agent with the default agent name from test_context ("test")
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test"  # matches default_agent from test config
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
        # Create worker (uses default agent from config)
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda platform, user_id: "test-session-123"

    # Worker should use the default agent from config
    assert worker.agent_def.id == "test"
    assert worker.agent_def.name == "Test Agent"


@pytest.mark.anyio
async def test_messagebus_worker_event_has_timestamp(test_context, tmp_path):
    """MessageBusWorker events include timestamp."""
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
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda platform, user_id: "test-session-123"
        test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        # Start worker
        task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify event has timestamp
        assert len(published_events) == 1
        event = published_events[0]
        assert event.timestamp > 0
        assert isinstance(event.timestamp, float)
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass
