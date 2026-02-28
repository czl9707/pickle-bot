# tests/events/test_websocket_stub.py
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from picklebot.server.websocket_worker import WebSocketWorker
from picklebot.events.types import Event, EventType, Source
from picklebot.events.bus import EventBus


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

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test",
        content="Hello",
        source=Source.agent("test"),
        timestamp=1.0,
    )

    # Should not raise
    await worker.handle_event(event)


def test_websocket_worker_subscribes_to_all_types(mock_context):
    worker = WebSocketWorker(mock_context)

    # WebSocketWorker auto-subscribes to all event types in __init__
    # Check subscriptions exist for all event types
    for event_type in EventType:
        assert len(mock_context.eventbus._subscribers[event_type]) == 1
