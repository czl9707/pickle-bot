# tests/events/test_types.py
import time
from dataclasses import dataclass

import pytest

from picklebot.core.events import (
    Event,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    AgentEventSource,
    CronEventSource,
    serialize_event,
    deserialize_event,
)
from picklebot.channel.telegram_channel import TelegramEventSource
from picklebot.core.events import CliEventSource


class TestEventBaseClass:
    """Tests for Event base class."""

    def test_event_has_auto_timestamp(self):
        """Event should auto-populate timestamp."""

        @dataclass
        class TestEvent(Event):
            pass

        before = time.time()
        event = TestEvent(
            session_id="s1",
            agent_id="a1",
            source=AgentEventSource(agent_id="test"),
            content="hello",
        )
        after = time.time()

        assert before <= event.timestamp <= after

    def test_event_to_dict_uses_class_name(self):
        """to_dict should use class name for type field."""

        @dataclass
        class TestEvent(Event):
            extra: str = ""

        event = TestEvent(
            session_id="s1",
            agent_id="a1",
            source=AgentEventSource(agent_id="test"),
            content="hello",
            timestamp=123.0,
            extra="foo",
        )

        result = event.to_dict()
        assert result["type"] == "TestEvent"
        assert result["session_id"] == "s1"
        assert result["timestamp"] == 123.0
        assert result["extra"] == "foo"

    def test_event_from_dict_excludes_type(self):
        """from_dict should work without type in constructor."""

        @dataclass
        class TestEvent(Event):
            extra: str = ""

        data = {
            "type": "TestEvent",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:test",
            "content": "hello",
            "timestamp": 123.0,
            "extra": "foo",
        }

        event = TestEvent.from_dict(data)
        assert event.session_id == "s1"
        assert event.extra == "foo"
        assert isinstance(event.source, AgentEventSource)


class TestInboundEvent:
    """Tests for InboundEvent."""

    def test_inbound_event_creation(self):
        source = TelegramEventSource(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Hello",
            timestamp=12345.0,
            retry_count=0,
        )
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert event.source.user_id == "123"
        assert event.content == "Hello"
        assert event.timestamp == 12345.0
        assert event.retry_count == 0

    def test_inbound_event_defaults(self):
        source = CliEventSource()
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Hi",
            timestamp=12345.0,
        )
        assert event.retry_count == 0

    def test_inbound_event_to_dict(self):
        source = TelegramEventSource(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Hello",
            timestamp=12345.0,
        )
        result = event.to_dict()
        assert result["type"] == "InboundEvent"
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "pickle"
        assert "context" not in result  # context field removed

    def test_inbound_event_from_dict(self):
        data = {
            "type": "InboundEvent",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "platform-telegram:123:456",
            "content": "Hello",
            "timestamp": 12345.0,
            "retry_count": 1,
        }
        event = InboundEvent.from_dict(data)
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert isinstance(event.source, TelegramEventSource)

    def test_inbound_event_roundtrip(self):
        """InboundEvent should serialize/deserialize correctly."""
        source = TelegramEventSource(user_id="user1", chat_id="chat1")
        original = InboundEvent(
            session_id="s1",
            agent_id="a1",
            source=source,
            content="hello",
            timestamp=123.0,
            retry_count=2,
        )
        data = original.to_dict()
        restored = InboundEvent.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.agent_id == original.agent_id
        assert restored.source.user_id == original.source.user_id
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
        assert restored.retry_count == original.retry_count


class TestOutboundEvent:
    """Tests for OutboundEvent."""

    def test_outbound_event_creation(self):
        source = AgentEventSource(agent_id="pickle")
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Response",
            timestamp=12345.0,
        )
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert event.error is None

    def test_outbound_event_with_error(self):
        source = AgentEventSource(agent_id="pickle")
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="",
            timestamp=12345.0,
            error="Something failed",
        )
        assert event.error == "Something failed"

    def test_outbound_event_serialization(self):
        source = AgentEventSource(agent_id="pickle")
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Response",
            timestamp=12345.0,
            error="test error",
        )
        data = event.to_dict()
        assert data["type"] == "OutboundEvent"
        assert data["error"] == "test error"

        restored = OutboundEvent.from_dict(data)
        assert restored.error == "test error"


class TestDispatchEvent:
    """Tests for DispatchEvent."""

    def test_dispatch_event_creation(self):
        source = AgentEventSource(agent_id="pickle")
        event = DispatchEvent(
            session_id="job-1",
            agent_id="cookie",
            source=source,
            content="Remember this",
            timestamp=12345.0,
            retry_count=0,
            parent_session_id="parent-sess-1",
        )
        assert event.session_id == "job-1"
        assert event.agent_id == "cookie"
        assert event.parent_session_id == "parent-sess-1"

    def test_dispatch_event_serialization(self):
        source = AgentEventSource(agent_id="pickle")
        event = DispatchEvent(
            session_id="job-1",
            agent_id="cookie",
            source=source,
            content="Task",
            timestamp=12345.0,
            parent_session_id="parent-1",
        )
        data = event.to_dict()
        assert data["type"] == "DispatchEvent"
        assert data["parent_session_id"] == "parent-1"

        restored = DispatchEvent.from_dict(data)
        assert restored.parent_session_id == "parent-1"


class TestDispatchResultEvent:
    """Tests for DispatchResultEvent."""

    def test_dispatch_result_event_creation(self):
        source = AgentEventSource(agent_id="cookie")
        event = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source=source,
            content="Done",
            timestamp=12345.0,
        )
        assert event.session_id == "job-1"
        assert event.error is None

    def test_dispatch_result_event_with_error(self):
        source = AgentEventSource(agent_id="cookie")
        event = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source=source,
            content="",
            timestamp=12345.0,
            error="Failed",
        )
        assert event.error == "Failed"


class TestAgentEventSourceDirect:
    """Tests for AgentEventSource construction."""

    def test_agent_event_source_creation(self):
        source = AgentEventSource(agent_id="pickle")
        assert source.agent_id == "pickle"
        assert str(source) == "agent:pickle"

    def test_agent_event_source_from_string(self):
        source = AgentEventSource.from_string("agent:pickle")
        assert source.agent_id == "pickle"


class TestCronEventSourceDirect:
    """Tests for CronEventSource construction."""

    def test_cron_event_source_creation(self):
        source = CronEventSource(cron_id="daily")
        assert source.cron_id == "daily"
        assert str(source) == "cron:daily"

    def test_cron_event_source_from_string(self):
        source = CronEventSource.from_string("cron:daily")
        assert source.cron_id == "daily"


class TestEventSourceSerialization:
    """Tests for EventSource serialization in events."""

    def test_inbound_event_with_agent_source(self):
        """InboundEvent should serialize/deserialize with AgentEventSource."""
        from picklebot.core.events import InboundEvent, AgentEventSource

        source = AgentEventSource(agent_id="pickle")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="hello",
        )

        data = event.to_dict()
        assert data["source"] == "agent:pickle"

        restored = InboundEvent.from_dict(data)
        assert isinstance(restored.source, AgentEventSource)
        assert restored.source.agent_id == "pickle"

    def test_inbound_event_with_platform_source(self):
        """InboundEvent should serialize/deserialize with platform sources."""
        from picklebot.core.events import InboundEvent
        from picklebot.channel.telegram_channel import TelegramEventSource

        source = TelegramEventSource(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="hello",
        )

        data = event.to_dict()
        assert data["source"] == "platform-telegram:123:456"

        restored = InboundEvent.from_dict(data)
        assert isinstance(restored.source, TelegramEventSource)
        assert restored.source.user_id == "123"
        assert restored.source.chat_id == "456"


def test_inbound_event_no_context_field():
    """InboundEvent should not have context field after refactor."""
    from picklebot.core.events import InboundEvent, AgentEventSource

    source = AgentEventSource(agent_id="pickle")
    event = InboundEvent(
        session_id="sess-1",
        agent_id="pickle",
        source=source,
        content="hello",
    )

    # Should not have context attribute
    assert not hasattr(event, "context")

    # Serialization should not include context
    data = event.to_dict()
    assert "context" not in data


class TestEventSerialization:
    """Tests for serialize/deserialize_event helpers."""

    def test_serialize_inbound_event(self):
        source = TelegramEventSource(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source=source,
            content="Hello",
            timestamp=12345.0,
        )
        data = serialize_event(event)
        assert data["type"] == "InboundEvent"
        assert "context" not in data  # context field removed

    def test_deserialize_inbound_event(self):
        data = {
            "type": "InboundEvent",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "platform-telegram:123:456",
            "content": "Hello",
            "timestamp": 12345.0,
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)
        assert event.agent_id == "pickle"
        assert isinstance(event.source, TelegramEventSource)

    def test_deserialize_outbound_event(self):
        data = {
            "type": "OutboundEvent",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "agent:pickle",
            "content": "Response",
            "timestamp": 12345.0,
            "error": "test",
        }
        event = deserialize_event(data)
        assert isinstance(event, OutboundEvent)
        assert event.error == "test"

    def test_deserialize_dispatch_event(self):
        data = {
            "type": "DispatchEvent",
            "session_id": "job-1",
            "agent_id": "cookie",
            "source": "agent:pickle",
            "content": "Task",
            "timestamp": 12345.0,
            "parent_session_id": "parent-1",
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchEvent)
        assert event.parent_session_id == "parent-1"

    def test_deserialize_dispatch_result_event(self):
        data = {
            "type": "DispatchResultEvent",
            "session_id": "job-1",
            "agent_id": "cookie",
            "source": "agent:cookie",
            "content": "Done",
            "timestamp": 12345.0,
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchResultEvent)

    def test_deserialize_unknown_event_type_raises_error(self):
        data = {
            "type": "unknown_type",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "agent:test",
            "content": "test",
            "timestamp": 12345.0,
        }
        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(data)

    def test_deserialize_uses_class_name_not_enum_value(self):
        """deserialize_event should use class names, not enum values."""
        # Should work with class name
        data = {
            "type": "InboundEvent",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:test",
            "content": "hello",
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)

        # Should fail with old enum value
        old_data = {
            "type": "inbound",  # Old enum value, not class name
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:test",
            "content": "hello",
        }
        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(old_data)
