# tests/events/test_bus_recovery.py
import json
import pytest
import asyncio
from unittest.mock import MagicMock

from picklebot.core.eventbus import EventBus
from picklebot.core.events import OutboundEvent


@pytest.fixture
def mock_context(tmp_path):
    context = MagicMock()
    context.config = MagicMock()
    context.config.event_path = tmp_path / ".events"
    return context


async def test_recover_republishes_pending_events(mock_context):
    # Create a pending event file manually
    pending_dir = mock_context.config.event_path / "pending"
    pending_dir.mkdir(parents=True)

    # Use OutboundEvent format (no metadata field)
    event_data = {
        "type": "OutboundEvent",
        "session_id": "test-session",
        "content": "Hello",
        "source": "agent:pickle",
        "timestamp": 12345.0,
        "error": None,
    }

    with open(pending_dir / "12345.0_test-session.json", "w") as f:
        json.dump(event_data, f)

    # Create bus and track received events
    received = []

    async def handler(event: OutboundEvent):
        received.append(event)

    bus = EventBus(mock_context)
    bus.subscribe(OutboundEvent, handler)

    # Start EventBus worker (which runs recovery on startup)
    eventbus_task = bus.start()

    try:
        # Allow recovery to complete
        await asyncio.sleep(0.1)

        # Event should have been recovered and dispatched
        assert len(received) == 1
        assert received[0].session_id == "test-session"
        assert received[0].content == "Hello"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


async def test_recover_empty_pending_dir(mock_context):
    bus = EventBus(mock_context)

    received = []

    async def handler(event: OutboundEvent):
        received.append(event)

    bus.subscribe(OutboundEvent, handler)

    # Start EventBus worker (which runs recovery on startup)
    eventbus_task = bus.start()

    try:
        await asyncio.sleep(0.1)

        assert len(received) == 0
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass
