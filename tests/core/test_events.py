"""Tests for refactored event system."""

import time
from dataclasses import dataclass
from picklebot.core.events import (
    Event,
    EventType,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    deserialize_event,
)


class TestEventBaseClass:
    """Tests for Event base class."""

    def test_event_has_auto_timestamp(self):
        """Event should auto-populate timestamp."""

        @dataclass
        class TestEvent(Event):
            @property
            def type(self) -> EventType:
                return EventType.INBOUND

        before = time.time()
        event = TestEvent(
            session_id="s1",
            agent_id="a1",
            source="test",
            content="hello",
        )
        after = time.time()

        assert before <= event.timestamp <= after

    def test_event_to_dict_includes_type(self):
        """to_dict should include event type."""

        @dataclass
        class TestEvent(Event):
            @property
            def type(self) -> EventType:
                return EventType.INBOUND

        event = TestEvent(
            session_id="s1",
            agent_id="a1",
            source="test",
            content="hello",
            timestamp=123.0,
        )

        result = event.to_dict()
        assert result["type"] == "inbound"
        assert result["session_id"] == "s1"
        assert result["timestamp"] == 123.0

    def test_event_from_dict_excludes_type(self):
        """from_dict should work without type in constructor."""

        @dataclass
        class TestEvent(Event):
            extra: str = ""

            @property
            def type(self) -> EventType:
                return EventType.INBOUND

        data = {
            "type": "inbound",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "test",
            "content": "hello",
            "timestamp": 123.0,
            "extra": "foo",
        }

        event = TestEvent.from_dict(data)
        assert event.session_id == "s1"
        assert event.extra == "foo"


class TestTypedEvents:
    """Tests for typed event classes."""

    def test_inbound_event_type_property(self):
        """InboundEvent.type should return INBOUND."""
        event = InboundEvent(
            session_id="s1",
            agent_id="a1",
            source="telegram:user1",
            content="hello",
        )
        assert event.type == EventType.INBOUND

    def test_outbound_event_type_property(self):
        """OutboundEvent.type should return OUTBOUND."""
        event = OutboundEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:pickle",
            content="response",
        )
        assert event.type == EventType.OUTBOUND

    def test_dispatch_event_type_property(self):
        """DispatchEvent.type should return DISPATCH."""
        event = DispatchEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:cookie",
            content="task",
            parent_session_id="parent1",
        )
        assert event.type == EventType.DISPATCH

    def test_dispatch_result_event_type_property(self):
        """DispatchResultEvent.type should return DISPATCH_RESULT."""
        event = DispatchResultEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:pickle",
            content="result",
        )
        assert event.type == EventType.DISPATCH_RESULT

    def test_inbound_event_to_dict_roundtrip(self):
        """InboundEvent should serialize/deserialize correctly."""
        original = InboundEvent(
            session_id="s1",
            agent_id="a1",
            source="telegram:user1",
            content="hello",
            timestamp=123.0,
            retry_count=2,
        )
        data = original.to_dict()
        restored = InboundEvent.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.agent_id == original.agent_id
        assert restored.source == original.source
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
        assert restored.retry_count == original.retry_count

    def test_outbound_event_with_error_to_dict_roundtrip(self):
        """OutboundEvent with error should serialize/deserialize correctly."""
        original = OutboundEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:pickle",
            content="response",
            timestamp=123.0,
            error="Something failed",
        )
        data = original.to_dict()
        restored = OutboundEvent.from_dict(data)

        assert restored.error == "Something failed"


class TestDeserializeEvent:
    """Tests for deserialize_event function."""

    def test_deserialize_inbound_event(self):
        """deserialize_event should create correct InboundEvent."""
        data = {
            "type": "inbound",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "telegram:user1",
            "content": "hello",
            "timestamp": 123.0,
            "retry_count": 1,
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)
        assert event.session_id == "s1"
        assert event.retry_count == 1

    def test_deserialize_outbound_event(self):
        """deserialize_event should create correct OutboundEvent."""
        data = {
            "type": "outbound",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:pickle",
            "content": "response",
            "timestamp": 123.0,
            "error": "test error",
        }
        event = deserialize_event(data)
        assert isinstance(event, OutboundEvent)
        assert event.error == "test error"

    def test_deserialize_dispatch_event(self):
        """deserialize_event should create correct DispatchEvent."""
        data = {
            "type": "dispatch",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:cookie",
            "content": "task",
            "timestamp": 123.0,
            "parent_session_id": "parent1",
            "retry_count": 0,
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchEvent)
        assert event.parent_session_id == "parent1"

    def test_deserialize_dispatch_result_event(self):
        """deserialize_event should create correct DispatchResultEvent."""
        data = {
            "type": "dispatch_result",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:sub",
            "content": "result",
            "timestamp": 123.0,
            "error": None,
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchResultEvent)

    def test_deserialize_unknown_type_raises(self):
        """deserialize_event should raise for unknown type."""
        data = {"type": "unknown", "session_id": "s1"}
        try:
            deserialize_event(data)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown event type" in str(e)
