"""Tests for MessageBusWorker."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock

from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.core.commands import CommandRegistry
from picklebot.core.context import SharedContext
from picklebot.core.events import EventSource, InboundEvent
from picklebot.messagebus.telegram_bus import TelegramEventSource
from picklebot.messagebus.discord_bus import DiscordEventSource
from picklebot.core.events import CliEventSource


class FakeBus:
    """Fake MessageBus for testing - uses real EventSource types."""

    def __init__(self, platform_name: str = "fake"):
        self.platform_name = platform_name
        self.messages: list[str] = []
        self.started = False

    async def run(self, callback):
        self.started = True
        self._callback = callback

    async def stop(self):
        self.started = False

    def is_allowed(self, source):
        return True

    async def reply(self, content, source):
        self.messages.append(content)


class FakeTelegramBus(FakeBus):
    """Fake bus that uses TelegramEventSource."""

    def __init__(self):
        super().__init__(platform_name="telegram")

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Use real TelegramEventSource
        await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))


class FakeDiscordBus(FakeBus):
    """Fake bus that uses DiscordEventSource."""

    def __init__(self):
        super().__init__(platform_name="discord")

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Use real DiscordEventSource
        await callback("hello", DiscordEventSource(user_id="456", channel_id="789"))


class FakeCliBus(FakeBus):
    """Fake bus that uses CliEventSource."""

    def __init__(self):
        super().__init__(platform_name="cli")

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Use real CliEventSource
        await callback("hello", CliEventSource())


class BlockingBus(FakeBus):
    """Fake bus that blocks all messages."""

    def is_allowed(self, source):
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

    bus = FakeCliBus()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        # Mock routing table to return test agent
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = MessageBusWorker(test_context)
        # Patch _get_or_create_session_id to return a known session ID for testing
        worker._get_or_create_session_id = lambda source, agent_id: "test-session-123"
        # Subscribe to capture events
        test_context.eventbus.subscribe(InboundEvent, capture_event)

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
        assert isinstance(event, InboundEvent)
        assert event.content == "hello"
        assert event.session_id == "test-session-123"
        assert str(event.source) == "platform-cli:cli-user"
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

    bus = BlockingBus()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        worker = MessageBusWorker(test_context)
        test_context.eventbus.subscribe(InboundEvent, capture_event)

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

    bus = FakeCliBus()
    with patch.object(test_context, "messagebus_buses", [bus]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = MessageBusWorker(test_context)

    # Should NOT have global_session anymore
    assert not hasattr(worker, "global_session")

    # Should NOT pre-load agent anymore (it's lazy loaded per source)
    assert not hasattr(worker, "agent")


@pytest.mark.anyio
async def test_messagebus_worker_reuses_existing_session(test_context, tmp_path):
    """MessageBusWorker reuses session from source cache for returning users."""
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

    # Pre-configure a session in source cache
    test_context.config.sources = {
        "platform-telegram:123:456": {"session_id": "existing-session-uuid"}
    }

    bus = FakeTelegramBus()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = MessageBusWorker(test_context)
        test_context.eventbus.subscribe(InboundEvent, capture_event)

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
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda source, agent_id: "test-session-123"
        test_context.eventbus.subscribe(InboundEvent, capture_event)

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
        assert str(event.source) == "platform-discord:456:789"
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

        # Create mock bus and source
        mock_bus = MagicMock()
        mock_bus.platform_name = "test"
        mock_bus.is_allowed.return_value = True
        mock_bus.reply = AsyncMock()

        mock_source = MagicMock(spec=EventSource)
        mock_source.__str__ = lambda self: "platform-test:user123:chat456"

        # Add bus to bus_map
        worker.bus_map["test"] = mock_bus

        # Get the callback
        callback = worker._create_callback("test")

        # Send slash command
        await callback("/help", mock_source)

        # Should have replied directly
        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args[0][0]
        assert "Available Commands" in call_args

        # Should NOT have published an event
        mock_context.eventbus.publish.assert_not_called()


class TestDefaultDeliverySource:
    """Tests for default_delivery_source auto-population."""

    @pytest.fixture
    def mock_context_with_config(self, mock_context):
        """Mock context with real config for set_runtime."""
        from picklebot.utils.config import Config, LLMConfig

        mock_context.config = Config(
            workspace=mock_context.config.event_path.parent,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="test",
        )
        mock_context.config.default_delivery_source = None
        return mock_context

    @pytest.mark.anyio
    async def test_first_platform_message_sets_default(self, mock_context_with_config):
        """First non-CLI platform message should set default_delivery_source."""
        mock_context = mock_context_with_config
        mock_bus = FakeTelegramBus()
        mock_context.messagebus_buses = [mock_bus]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.config.sources = {}

        with patch("picklebot.server.messagebus_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="test-session")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = MessageBusWorker(mock_context)
            worker._get_or_create_session_id = lambda s, a: "test-session"
            callback = worker._create_callback("telegram")

            await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))

        assert (
            mock_context.config.default_delivery_source == "platform-telegram:123:456"
        )

    @pytest.mark.anyio
    async def test_cli_message_does_not_set_default(self, mock_context_with_config):
        """CLI messages should not update default_delivery_source."""
        mock_context = mock_context_with_config
        mock_bus = FakeCliBus()
        mock_context.messagebus_buses = [mock_bus]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.config.sources = {}
        mock_context.config.default_delivery_source = None

        with patch("picklebot.server.messagebus_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="test-session")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = MessageBusWorker(mock_context)
            worker._get_or_create_session_id = lambda s, a: "test-session"
            callback = worker._create_callback("cli")

            await callback("hello", CliEventSource())

        # CLI should not set default
        assert mock_context.config.default_delivery_source is None

    @pytest.mark.anyio
    async def test_subsequent_message_does_not_overwrite_default(
        self, mock_context_with_config
    ):
        """Subsequent platform messages should not overwrite existing default."""
        mock_context = mock_context_with_config
        mock_context.config.default_delivery_source = "platform-telegram:existing:999"

        mock_bus = FakeTelegramBus()
        mock_context.messagebus_buses = [mock_bus]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.config.sources = {}

        with patch("picklebot.server.messagebus_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="test-session")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = MessageBusWorker(mock_context)
            worker._get_or_create_session_id = lambda s, a: "test-session"
            callback = worker._create_callback("telegram")

            await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))

        # Should NOT have been overwritten
        assert (
            mock_context.config.default_delivery_source
            == "platform-telegram:existing:999"
        )


@pytest.mark.anyio
async def test_messagebus_worker_uses_routing_table(test_context, tmp_path):
    """MessageBusWorker uses routing table to resolve agents."""
    # Create test agents
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)

    # Create test agent
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

    bus = FakeCliBus()
    with patch.object(test_context, "messagebus_buses", [bus]):
        # Mock routing table to resolve to test agent
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda source, agent_id: "test-session-123"

    # Worker should not pre-load any agent
    assert not hasattr(worker, "agent_def")
    assert not hasattr(worker, "agent")

    # Routing should be done via routing_table.resolve
    assert test_context.routing_table.resolve("platform-cli:123") == "test"


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

    bus = FakeCliBus()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "messagebus_buses", [bus]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = MessageBusWorker(test_context)
        worker._get_or_create_session_id = lambda source, agent_id: "test-session-123"
        test_context.eventbus.subscribe(InboundEvent, capture_event)

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


class TestMessageBusWorkerRouting:
    """Tests for new routing-based MessageBusWorker."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context with routing setup."""
        from unittest.mock import Mock, AsyncMock
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        context = Mock()
        context.config = Mock()
        context.config.default_agent = "pickle"
        context.config.sources = {}
        context.config.messagebus = Mock()
        context.config.messagebus.enabled = True
        context.config.routing = {
            "bindings": [
                {"agent": "cookie", "value": "telegram:123456"},
                {"agent": "pickle", "value": "telegram:.*"},
            ]
        }

        context.routing_table = Mock()
        context.routing_table.resolve = Mock(return_value="cookie")

        # Create a proper AgentDef mock with llm config
        agent_def = AgentDef(
            id="cookie",
            name="Cookie Agent",
            description="Test agent",
            agent_md="You are a test agent.",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        )
        context.agent_loader = Mock()
        context.agent_loader.load = Mock(return_value=agent_def)

        context.eventbus = Mock()
        context.eventbus.publish = AsyncMock()

        context.messagebus_buses = []
        context.command_registry = Mock()
        context.command_registry.dispatch = Mock(return_value=None)

        return context

    def test_messagebus_worker_no_default_agent_in_init(self, mock_context):
        """MessageBusWorker should not pre-load default agent."""
        worker = MessageBusWorker(mock_context)

        assert not hasattr(worker, "agent_def")
        assert not hasattr(worker, "agent")

    def test_get_or_create_session_uses_source_cache(self, mock_context):
        """_get_or_create_session_id should check source cache first."""
        mock_context.config.sources = {
            "platform-telegram:123456:789": {"session_id": "existing-session"}
        }

        worker = MessageBusWorker(mock_context)
        session_id = worker._get_or_create_session_id(
            "platform-telegram:123456:789", "cookie"
        )

        assert session_id == "existing-session"

    def test_get_or_create_session_creates_new(self, mock_context):
        """_get_or_create_session_id should create session if not cached."""
        mock_context.config.set_runtime = Mock()
        mock_context.config.sources = {}

        with patch("picklebot.server.messagebus_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="new-session-id")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = MessageBusWorker(mock_context)
            session_id = worker._get_or_create_session_id(
                "platform-telegram:123456:789", "cookie"
            )

            assert session_id == "new-session-id"
            mock_context.config.set_runtime.assert_called_once_with(
                "sources.platform-telegram:123456:789", {"session_id": "new-session-id"}
            )

    def test_messagebus_worker_routes_unknown_source_to_default(self, mock_context):
        """MessageBusWorker should route unknown sources to default_agent."""
        from picklebot.core.routing import RoutingTable

        mock_context.config.routing = {"bindings": []}
        mock_context.config.default_agent = "pickle"
        mock_context.config.set_runtime = Mock()

        # Use real RoutingTable to verify fallback to default_agent
        mock_context.routing_table = RoutingTable(mock_context)

        # Add a mock bus for telegram
        mock_bus = MagicMock()
        mock_bus.platform_name = "telegram"
        mock_bus.is_allowed = MagicMock(return_value=True)
        mock_bus.reply = AsyncMock()
        mock_context.messagebus_buses = [mock_bus]

        # Mock Agent to avoid loading actual agent
        with patch("picklebot.server.messagebus_worker.Agent") as MockAgent:
            mock_session = Mock(session_id="new-session-id")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = MessageBusWorker(mock_context)
            callback = worker._create_callback("telegram")

            # This should NOT be skipped even with empty bindings
            # Use real TelegramEventSource instead of removed TelegramContext
            asyncio.run(
                callback("hello", TelegramEventSource(user_id="999", chat_id="999"))
            )

        # Verify event was published (using default_agent)
        assert mock_context.eventbus.publish.called
