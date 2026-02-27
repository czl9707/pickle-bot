# tests/events/test_websocket_stub.py
import pytest
from unittest.mock import MagicMock

from picklebot.events.websocket import WebSocketWorker
from picklebot.events.types import Event, EventType
from picklebot.events.bus import EventBus


@pytest.fixture
def mock_context():
    return MagicMock()


def test_websocket_worker_creation(mock_context):
    worker = WebSocketWorker(mock_context)
    assert worker.context == mock_context


@pytest.mark.asyncio
async def test_websocket_worker_handles_event(mock_context):
    worker = WebSocketWorker(mock_context)

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test",
        content="Hello",
        source="agent",
        timestamp=1.0,
    )

    # Should not raise
    await worker.handle_event(event)


def test_websocket_worker_subscribes_to_all_types(mock_context):
    worker = WebSocketWorker(mock_context)
    bus = EventBus()

    worker.subscribe(bus)

    # Check subscriptions exist
    assert len(bus._subscribers[EventType.INBOUND]) == 1
    assert len(bus._subscribers[EventType.OUTBOUND]) == 1
    assert len(bus._subscribers[EventType.STATUS]) == 1
