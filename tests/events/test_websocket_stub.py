# tests/events/test_websocket_stub.py
import pytest
from unittest.mock import MagicMock

from picklebot.server.websocket_worker import WebSocketWorker
from picklebot.core.events import OutboundEvent, EventType, Source
from picklebot.core.eventbus import EventBus


@pytest.fixture
def mock_context(tmp_path):
    context = MagicMock()
    context.config = MagicMock()
    context.config.event_path = tmp_path / ".events"
    context.eventbus = EventBus(context)
    return context


def test_websocket_worker_creation(mock_context):
    worker = WebSocketWorker(mock_context)
    assert worker.context == mock_context


@pytest.mark.asyncio
async def test_websocket_worker_handles_event(mock_context):
    worker = WebSocketWorker(mock_context)

    event = OutboundEvent(
        session_id="test",
        agent_id="test",
        content="Hello",
        source=Source.agent("test"),
        timestamp=1.0,
    )

    # Should not raise
    await worker.handle_event(event)


def test_websocket_worker_subscribes_to_all_types(mock_context):
    _ = WebSocketWorker(mock_context)  # noqa: F841 - created for side effect

    # WebSocketWorker auto-subscribes to all event types in __init__
    # Check subscriptions exist for all event types
    for event_type in EventType:
        assert len(mock_context.eventbus._subscribers[event_type]) == 1
