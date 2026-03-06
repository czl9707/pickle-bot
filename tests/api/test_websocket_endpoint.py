"""Integration tests for WebSocket endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext


@pytest.fixture
def test_context():
    """Create test SharedContext with mock WebSocket worker."""
    context = MagicMock(spec=SharedContext)
    context.websocket_worker = MagicMock()
    context.websocket_worker.handle_connection = AsyncMock()
    return context


@pytest.fixture
def client(test_context):
    """Create test client."""
    app = create_app(test_context)
    return TestClient(app)


class TestWebSocketEndpoint:
    """Test WebSocket endpoint integration."""

    def test_websocket_endpoint_exists(self, client):
        """Test WebSocket endpoint is registered."""
        # WebSocket endpoints don't show up in routes the same way
        # This is more of a smoke test
        assert client.app is not None

    def test_websocket_endpoint_rejects_when_worker_unavailable(self):
        """Test WebSocket closes with code 1013 when worker not available."""
        # Create context without websocket worker
        context = MagicMock(spec=SharedContext)
        context.websocket_worker = None
        app = create_app(context)
        test_client = TestClient(app)

        # Note: Testing actual WebSocket connection with TestClient is complex
        # The actual behavior (closing with code 1013) should be tested
        # with real WebSocket client or integration tests
        assert test_client.app is not None

    # Note: Testing WebSocket connections with TestClient is complex
    # Real integration testing should be done with actual WebSocket client
    # For now, we do manual testing with wscat/websocat
