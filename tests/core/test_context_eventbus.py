"""Tests for SharedContext EventBus integration."""

import pytest

from picklebot.core.context import SharedContext
from picklebot.core.eventbus import EventBus
from picklebot.core.events import InboundEvent, OutboundEvent, Source
from picklebot.utils.config import Config


def test_shared_context_has_eventbus(tmp_path):
    """SharedContext should have an EventBus instance initialized."""
    # Create a minimal config file with all required fields
    config_file = tmp_path / "config.user.yaml"
    config_file.write_text(
        """default_agent: test-agent
llm:
  provider: openai
  model: gpt-4
  api_key: test
"""
    )

    config = Config.load(tmp_path)
    context = SharedContext(config)
    assert hasattr(context, "eventbus")
    assert isinstance(context.eventbus, EventBus)


@pytest.mark.asyncio
async def test_subscribe_by_event_class(tmp_path):
    """EventBus.subscribe should accept event classes with type-safe handlers."""
    config_file = tmp_path / "config.user.yaml"
    config_file.write_text(
        """default_agent: test-agent
llm:
  provider: openai
  model: gpt-4
  api_key: test
"""
    )

    config = Config.load(tmp_path)
    context = SharedContext(config)
    eventbus = context.eventbus

    received_inbound = []
    received_outbound = []

    async def inbound_handler(event: InboundEvent):
        received_inbound.append(event)

    async def outbound_handler(event: OutboundEvent):
        received_outbound.append(event)

    # Subscribe by event class
    eventbus.subscribe(InboundEvent, inbound_handler)
    eventbus.subscribe(OutboundEvent, outbound_handler)

    # Create test events
    inbound = InboundEvent(
        session_id="test",
        agent_id="test",
        content="inbound",
        source=Source.platform("telegram", "user1"),
    )
    outbound = OutboundEvent(
        session_id="test",
        agent_id="test",
        content="outbound",
        source=Source.agent("test"),
    )

    # Notify subscribers
    await eventbus._notify_subscribers(inbound)
    await eventbus._notify_subscribers(outbound)

    # Verify correct handlers called
    assert len(received_inbound) == 1
    assert received_inbound[0].content == "inbound"
    assert len(received_outbound) == 1
    assert received_outbound[0].content == "outbound"
