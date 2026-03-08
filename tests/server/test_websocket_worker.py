"""Tests for WebSocketWorker."""

import pytest
from unittest.mock import Mock, AsyncMock
from picklebot.server.websocket_worker import WebSocketWorker
from picklebot.api.schemas import WebSocketMessage
from picklebot.core.events import WebSocketEventSource, InboundEvent


class TestWebSocketWorker:
    """Test WebSocketWorker functionality."""

    @pytest.fixture
    def mock_context(self):
        """Create mock SharedContext."""
        context = Mock()
        context.eventbus = Mock()
        context.eventbus.subscribe = Mock()
        context.eventbus.publish = AsyncMock()
        context.config = Mock()
        context.config.sources = {}
        context.config.set_runtime = Mock()
        context.routing_table = Mock()
        context.routing_table.resolve = Mock(return_value="pickle")
        context.routing_table.get_or_create_session_id = Mock(
            return_value="session-abc"
        )
        context.agent_loader = Mock()
        return context

    @pytest.fixture
    def worker(self, mock_context):
        """Create WebSocketWorker instance."""
        return WebSocketWorker(mock_context)

    def test_worker_initialization(self, worker):
        """Test worker initializes with empty client set."""
        assert worker.clients == set()
        assert worker.context is not None

    def test_worker_subscribes_to_all_events(self, mock_context):
        """Test worker subscribes to all event types."""
        WebSocketWorker(mock_context)

        # Should subscribe to 4 event types
        assert mock_context.eventbus.subscribe.call_count == 4

    async def test_handle_connection_adds_client(self, worker):
        """Test handle_connection adds client to set."""
        mock_ws = Mock()
        mock_ws.receive_json = AsyncMock(side_effect=RuntimeError("Mocked error"))

        # Call handle_connection - this will trigger the try/finally
        # Client is added first, then loop runs
        await worker.handle_connection(mock_ws)

        # After error, client should be removed by finally block
        assert mock_ws not in worker.clients

    async def test_handle_connection_removes_client_on_exit(self, worker):
        """Test handle_connection removes client when done."""
        mock_ws = Mock()
        mock_ws.receive_json = AsyncMock(side_effect=Exception("Disconnect"))

        await worker.handle_connection(mock_ws)
        assert mock_ws not in worker.clients

    def test_normalize_message_with_agent_id(self, worker):
        """Test normalizing message with explicit agent_id."""
        msg = WebSocketMessage(source="user-123", content="Hello!", agent_id="pickle")

        event = worker._normalize_message(msg)

        assert isinstance(event, InboundEvent)
        assert event.content == "Hello!"
        assert isinstance(event.source, WebSocketEventSource)
        assert event.source.user_id == "user-123"
        assert event.session_id == "session-abc"
        # Verify routing_table method was called
        worker.context.routing_table.get_or_create_session_id.assert_called_once()

    def test_normalize_message_without_agent_id(self, worker, mock_context):
        """Test normalizing message without agent_id (uses routing)."""
        msg = WebSocketMessage(source="user-456", content="Hello!", agent_id=None)

        # Mock routing to return specific agent
        mock_context.routing_table.resolve = Mock(return_value="cookie")
        mock_context.routing_table.get_or_create_session_id = Mock(
            return_value="session-xyz"
        )

        event = worker._normalize_message(msg)

        assert event.session_id == "session-xyz"
        mock_context.routing_table.resolve.assert_called_once_with(
            "platform-ws:user-456"
        )
        mock_context.routing_table.get_or_create_session_id.assert_called_once()
