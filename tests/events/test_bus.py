# tests/events/test_bus.py
import pytest
from picklebot.core.events import Event, OutboundEvent, InboundEvent, AgentEventSource
from picklebot.channel.telegram_channel import TelegramEventSource


@pytest.fixture
def event_bus(test_context):
    return test_context.eventbus


def test_event_bus_creation(event_bus):
    assert event_bus is not None
    assert event_bus._subscribers == {}


@pytest.mark.asyncio
async def test_subscribe_and_notify(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(OutboundEvent, handler)

    event = OutboundEvent(
        session_id="test-session",
        agent_id="pickle",
        content="Hello",
        source=AgentEventSource(agent_id="pickle"),
        timestamp=12345.0,
    )

    await event_bus._notify_subscribers(event)

    assert len(received) == 1
    assert received[0] == event


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus):
    received_1 = []
    received_2 = []

    async def handler_1(event: Event):
        received_1.append(event)

    async def handler_2(event: Event):
        received_2.append(event)

    event_bus.subscribe(OutboundEvent, handler_1)
    event_bus.subscribe(OutboundEvent, handler_2)

    event = OutboundEvent(
        session_id="test-session",
        agent_id="pickle",
        content="Hello",
        source=AgentEventSource(agent_id="pickle"),
        timestamp=12345.0,
    )

    await event_bus._notify_subscribers(event)

    assert len(received_1) == 1
    assert len(received_2) == 1


@pytest.mark.asyncio
async def test_unsubscribe(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(OutboundEvent, handler)
    event_bus.unsubscribe(handler)

    event = OutboundEvent(
        session_id="test-session",
        agent_id="pickle",
        content="Hello",
        source=AgentEventSource(agent_id="pickle"),
        timestamp=12345.0,
    )

    await event_bus._notify_subscribers(event)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_subscribe_to_multiple_types(event_bus):
    received_outbound = []
    received_inbound = []

    async def outbound_handler(event: Event):
        received_outbound.append(event)

    async def inbound_handler(event: Event):
        received_inbound.append(event)

    event_bus.subscribe(OutboundEvent, outbound_handler)
    event_bus.subscribe(InboundEvent, inbound_handler)

    outbound_event = OutboundEvent(
        session_id="test",
        agent_id="test",
        content="Out",
        source=AgentEventSource(agent_id="test"),
        timestamp=1.0,
    )
    inbound_event = InboundEvent(
        session_id="test",
        agent_id="test",
        content="In",
        source=TelegramEventSource(user_id="user1", chat_id="chat1"),
        timestamp=2.0,
    )

    await event_bus._notify_subscribers(outbound_event)
    await event_bus._notify_subscribers(inbound_event)

    assert len(received_outbound) == 1
    assert len(received_inbound) == 1
