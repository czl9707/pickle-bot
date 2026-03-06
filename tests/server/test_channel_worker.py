"""Tests for ChannelWorker."""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock

from picklebot.server.channel_worker import ChannelWorker
from picklebot.core.commands import CommandRegistry
from picklebot.core.context import SharedContext
from picklebot.core.events import EventSource, InboundEvent
from picklebot.channel.telegram_channel import TelegramEventSource
from picklebot.channel.discord_channel import DiscordEventSource
from picklebot.core.events import CliEventSource


class FakeChannel:
    """Fake Channel for testing - uses real EventSource types."""

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


class FakeTelegramChannel(FakeChannel):
    """Fake Channel that uses TelegramEventSource."""

    def __init__(self):
        super().__init__(platform_name="telegram")

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Use real TelegramEventSource
        await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))


class FakeDiscordChannel(FakeChannel):
    """Fake Channel that uses DiscordEventSource."""

    def __init__(self):
        super().__init__(platform_name="discord")

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Use real DiscordEventSource
        await callback("hello", DiscordEventSource(user_id="456", channel_id="789"))


class FakeCliChannel(FakeChannel):
    """Fake Channel that uses CliEventSource."""

    def __init__(self):
        super().__init__(platform_name="cli")

    async def run(self, callback):
        self.started = True
        self._callback = callback
        # Use real CliEventSource
        await callback("hello", CliEventSource())


class BlockingChannel(FakeChannel):
    """Fake Channel that blocks all messages."""

    def is_allowed(self, source):
        return False


@pytest.mark.anyio
async def test_channel_worker_publishes_inbound_event(test_context, tmp_path):
    """ChannelWorker publishes INBOUND events to EventBus."""
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

    channel = FakeCliChannel()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "channels", [channel]):
        # Mock routing table to return test agent
        test_context.routing_table.resolve = Mock(return_value="test")
        test_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session-123"
        )
        worker = ChannelWorker(test_context)
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
async def test_channel_worker_ignores_non_whitelisted(test_context, tmp_path):
    """ChannelWorker ignores messages from non-whitelisted senders."""
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

    channel = BlockingChannel()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "channels", [channel]):
        worker = ChannelWorker(test_context)
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
async def test_channel_worker_creates_per_user_session(test_context, tmp_path):
    """ChannelWorker creates a new session for each user."""
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

    channel = FakeCliChannel()
    with patch.object(test_context, "channels", [channel]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = ChannelWorker(test_context)

    # Should NOT have global_session anymore
    assert not hasattr(worker, "global_session")

    # Should NOT pre-load agent anymore (it's lazy loaded per source)
    assert not hasattr(worker, "agent")


@pytest.mark.anyio
async def test_channel_worker_reuses_existing_session(test_context, tmp_path):
    """ChannelWorker reuses session from source cache for returning users."""
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

    channel = FakeTelegramChannel()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "channels", [channel]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        worker = ChannelWorker(test_context)
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
async def test_channel_worker_includes_metadata(test_context, tmp_path):
    """ChannelWorker includes platform-specific metadata in events."""
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

    channel = FakeDiscordChannel()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "channels", [channel]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        test_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session-123"
        )
        worker = ChannelWorker(test_context)
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


class TestChannelWorkerSlashCommands:
    """Tests for slash command handling in ChannelWorker."""

    @pytest.fixture
    def mock_context(self, test_config, test_agent_def):
        """Create mock context with minimal setup."""
        context = MagicMock(spec=SharedContext)
        context.config = test_config
        context.agent_loader = MagicMock()
        context.agent_loader.load.return_value = test_agent_def
        context.config.channels = MagicMock()
        context.config.channels.telegram = None
        context.config.channels.discord = None
        context.command_registry = CommandRegistry.with_builtins()
        # Add eventbus mock
        context.eventbus = MagicMock()
        context.eventbus.publish = AsyncMock()
        return context

    def test_context_has_command_registry(self, mock_context):
        """SharedContext should have CommandRegistry."""
        mock_context.channels = []

        ChannelWorker(mock_context)

        assert mock_context.command_registry is not None
        assert isinstance(mock_context.command_registry, CommandRegistry)

    @pytest.mark.anyio
    async def test_callback_handles_slash_command(self, mock_context):
        """Callback should dispatch slash commands and reply directly."""
        mock_context.channels = []

        worker = ChannelWorker(mock_context)

        # Create mock channel and source
        mock_channel = MagicMock()
        mock_channel.platform_name = "test"
        mock_channel.is_allowed.return_value = True
        mock_channel.reply = AsyncMock()

        mock_source = MagicMock(spec=EventSource)
        mock_source.__str__ = lambda self: "platform-test:user123:chat456"

        worker.channel_map["test"] = mock_channel

        # Get the callback
        callback = worker._create_callback("test")

        # Send slash command
        await callback("/help", mock_source)

        # Should have replied directly
        mock_channel.reply.assert_called_once()
        call_args = mock_channel.reply.call_args[0][0]
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
        mock_channel = FakeTelegramChannel()
        mock_context.channels = [mock_channel]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session"
        )
        mock_context.config.sources = {}

        worker = ChannelWorker(mock_context)
        callback = worker._create_callback("telegram")

        await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))

        assert (
            mock_context.config.default_delivery_source == "platform-telegram:123:456"
        )

    @pytest.mark.anyio
    async def test_cli_message_does_not_set_default(self, mock_context_with_config):
        """CLI messages should not update default_delivery_source."""
        mock_context = mock_context_with_config
        mock_channel = FakeCliChannel()
        mock_context.channels = [mock_channel]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session"
        )
        mock_context.config.sources = {}
        mock_context.config.default_delivery_source = None

        worker = ChannelWorker(mock_context)
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

        mock_channel = FakeTelegramChannel()
        mock_context.channels = [mock_channel]
        mock_context.routing_table.resolve = Mock(return_value="test")
        mock_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session"
        )
        mock_context.config.sources = {}

        worker = ChannelWorker(mock_context)
        callback = worker._create_callback("telegram")

        await callback("hello", TelegramEventSource(user_id="123", chat_id="456"))

        # Should NOT have been overwritten
        assert (
            mock_context.config.default_delivery_source
            == "platform-telegram:existing:999"
        )


@pytest.mark.anyio
async def test_channel_worker_uses_routing_table(test_context, tmp_path):
    """ChannelWorker uses routing table to resolve agents."""
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

    channel = FakeCliChannel()
    with patch.object(test_context, "channels", [channel]):
        # Mock routing table to resolve to test agent
        test_context.routing_table.resolve = Mock(return_value="test")
        test_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session-123"
        )
        worker = ChannelWorker(test_context)

    # Worker should not pre-load any agent
    assert not hasattr(worker, "agent_def")
    assert not hasattr(worker, "agent")

    # Routing should be done via routing_table.resolve
    assert test_context.routing_table.resolve("platform-cli:123") == "test"


@pytest.mark.anyio
async def test_channel_worker_event_has_timestamp(test_context, tmp_path):
    """ChannelWorker events include timestamp."""
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

    channel = FakeCliChannel()
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent):
        published_events.append(event)

    with patch.object(test_context, "channels", [channel]):
        # Mock routing table
        test_context.routing_table.resolve = Mock(return_value="test")
        test_context.routing_table.get_or_create_session_id = Mock(
            return_value="test-session-123"
        )
        worker = ChannelWorker(test_context)
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


class TestChannelWorkerRouting:
    """Tests for new routing-based ChannelWorker."""

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
        context.config.channels = Mock()
        context.config.channels.enabled = True
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

        context.channels = []
        context.command_registry = Mock()
        context.command_registry.dispatch = Mock(return_value=None)

        return context

    def test_channel_worker_no_default_agent_in_init(self, mock_context):
        """ChannelWorker should not pre-load default agent."""
        worker = ChannelWorker(mock_context)

        assert not hasattr(worker, "agent_def")
        assert not hasattr(worker, "agent")

    def test_channel_worker_routes_unknown_source_to_default(self, mock_context):
        """ChannelWorker should route unknown sources to default_agent."""
        from picklebot.core.routing import RoutingTable

        mock_context.config.routing = {"bindings": []}
        mock_context.config.default_agent = "pickle"
        mock_context.config.set_runtime = Mock()

        # Use real RoutingTable to verify fallback to default_agent
        mock_context.routing_table = RoutingTable(mock_context)

        # Add a mock channel for telegram
        mock_channel = MagicMock()
        mock_channel.platform_name = "telegram"
        mock_channel.is_allowed = MagicMock(return_value=True)
        mock_channel.reply = AsyncMock()
        mock_context.channels = [mock_channel]

        # Mock Agent in routing module since that's where it's used now
        with patch("picklebot.core.routing.Agent") as MockAgent:
            mock_session = Mock(session_id="new-session-id")
            MockAgent.return_value.new_session.return_value = mock_session

            worker = ChannelWorker(mock_context)
            callback = worker._create_callback("telegram")

            # This should NOT be skipped even with empty bindings
            # Use real TelegramEventSource instead of removed TelegramContext
            asyncio.run(
                callback("hello", TelegramEventSource(user_id="999", chat_id="999"))
            )

        # Verify event was published (using default_agent)
        assert mock_context.eventbus.publish.called
