"""Tests for WebSocketWorker."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
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
        context.eventbus.emit = AsyncMock()
        context.config = Mock()
        context.config.api = Mock()
        context.config.api.enabled = True
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
        worker = WebSocketWorker(mock_context)

        # Should subscribe to 4 event types
        assert mock_context.eventbus.subscribe.call_count == 4

    @pytest.mark.asyncio
    async def test_handle_connection_adds_client(self, worker):
        """Test handle_connection adds client to set."""
        mock_ws = Mock()
        mock_ws.accept = AsyncMock()

        # Mock receive_json to be an async generator that immediately stops
        async def mock_receive():
            raise RuntimeError("Mocked error")
            return
            yield

        mock_ws.receive_json = Mock(side_effect=mock_receive)

        with patch.object(worker, "_run_client_loop"):
            # Just test that the client is added
            mock_ws.accept.assert_called_once()

            # Check that client was added
            assert mock_ws in worker.clients

            # Let the context through
            await asyncio.sleep(0.01)

            # Verify cleanup still works
            assert mock_ws not in worker.clients
        assert mock_ws.accept.called

    @pytest.mark.asyncio
    async def test_handle_connection_removes_client_on_exit(self, worker):
        """Test handle_connection removes client when done."""
        mock_ws = Mock()
        mock_ws.receive_json = AsyncMock(side_effect=Exception("Disconnect"))

        await worker.handle_connection(mock_ws)

        assert mock_ws not in worker.clients

    def test_normalize_message_with_agent_id(self, worker):
        """Test normalizing message with explicit agent_id."""
        msg = WebSocketMessage(source="user-123", content="Hello!", agent_id="pickle")

        # Mock routing/session methods (will be implemented later)
        worker._get_or_create_session = Mock(return_value="session-abc")

        event = worker._normalize_message(msg)

        assert isinstance(event, InboundEvent)
        assert event.agent_id == "pickle"
        assert event.content == "Hello!"
        assert isinstance(event.source, WebSocketEventSource)
        assert event.source.user_id == "user-123"

    def test_normalize_message_without_agent_id(self, worker):
        """Test normalizing message without agent_id (uses routing)."""
        msg = WebSocketMessage(source="user-456", content="Hello!", agent_id=None)

        # Mock routing to return specific agent
        worker._route_message = Mock(return_value="cookie")
        worker._get_or_create_session = Mock(return_value="session-xyz")

        event = worker._normalize_message(msg)

        assert event.agent_id == "cookie"
        worker._route_message.assert_called_once_with("user-456", "Hello!")
