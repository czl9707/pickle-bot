# tests/events/test_bus_persistence.py

import asyncio
import json
import pytest
from picklebot.core.events import Event, OutboundEvent, InboundEvent, AgentEventSource
from picklebot.channel.telegram_channel import TelegramEventSource


@pytest.fixture
def event_bus(test_context):
    return test_context.eventbus


@pytest.fixture
def events_dir(test_context):
    return test_context.config.event_path


def test_event_bus_has_persistence_dir(event_bus, events_dir):
    assert event_bus.pending_dir == events_dir / "pending"


async def test_persist_outbound_event(event_bus, events_dir):
    event = OutboundEvent(
        session_id="test-session",
        content="Hello",
        source=AgentEventSource(agent_id="pickle"),
        timestamp=12345.0,
    )

    await event_bus._persist_outbound(event)

    # Check file was created
    pending_files = list((events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 1

    # Verify content
    with open(pending_files[0]) as f:
        data = json.load(f)
    assert data["session_id"] == "test-session"
    assert data["content"] == "Hello"


async def test_persist_skips_non_outbound(event_bus, events_dir):
    inbound_event = InboundEvent(
        session_id="test-session",
        content="Hi",
        source=TelegramEventSource(user_id="user1", chat_id="chat1"),
        timestamp=12345.0,
    )

    await event_bus._persist_outbound(inbound_event)

    # No files should be created
    pending_files = list((events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 0


async def test_ack_deletes_persisted_event(event_bus, events_dir):
    event = OutboundEvent(
        session_id="test-session",
        content="Hello",
        source=AgentEventSource(agent_id="pickle"),
        timestamp=12345.0,
    )
    await event_bus._persist_outbound(event)

    # Verify file was created
    pending_files = list((events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 1

    # Ack the event (now takes event instead of filename)
    event_bus.ack(event)

    # File should be deleted
    pending_files = list((events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 0


async def test_atomic_write(event_bus, events_dir):
    """Test that files are written atomically (tmp + fsync + rename)."""
    event = OutboundEvent(
        session_id="test-session",
        content="Hello",
        source=AgentEventSource(agent_id="pickle"),
        timestamp=12345.0,
    )
    await event_bus._persist_outbound(event)

    # No temp files should remain
    tmp_files = list((events_dir / "pending").glob(".tmp.*"))
    assert len(tmp_files) == 0

    # Only final file should exist
    json_files = list((events_dir / "pending").glob("*.json"))
    assert len(json_files) == 1


async def test_publish_outbound_persists_and_notifies(event_bus, events_dir):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(OutboundEvent, handler)

    # Start EventBus worker to process queued events
    eventbus_task = event_bus.start()

    try:
        event = OutboundEvent(
            session_id="test-session",
            content="Hello",
            source=AgentEventSource(agent_id="pickle"),
            timestamp=12345.0,
        )
        await event_bus.publish(event)

        # Allow async tasks to complete
        await asyncio.sleep(0.1)

        # Should have persisted
        pending_files = list((events_dir / "pending").glob("*.json"))
        assert len(pending_files) == 1

        # Should have notified subscriber
        assert len(received) == 1
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


async def test_publish_inbound_no_persist_inbound(event_bus, events_dir):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(InboundEvent, handler)

    # Start EventBus worker to process queued events
    eventbus_task = event_bus.start()

    try:
        event = InboundEvent(
            session_id="test-session",
            content="Hi",
            source=TelegramEventSource(user_id="user1", chat_id="chat1"),
            timestamp=12345.0,
        )
        await event_bus.publish(event)

        await asyncio.sleep(0.1)

        # Should NOT have persisted
        pending_files = list((events_dir / "pending").glob("*.json"))
        assert len(pending_files) == 0

        # Should have notified subscriber
        assert len(received) == 1
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass
