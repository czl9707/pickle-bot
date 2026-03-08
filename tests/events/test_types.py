"""Tests for Event types."""

import pytest

from picklebot.core.events import (
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    AgentEventSource,
    serialize_event,
    deserialize_event,
)
from picklebot.channel.telegram_channel import TelegramEventSource


class TestEventRoundtrip:
    """Parametrized roundtrip tests for all Event types."""

    @pytest.mark.parametrize(
        "event_cls,extra_args",
        [
            (InboundEvent, {"retry_count": 0}),
            (OutboundEvent, {"error": None}),
            (DispatchEvent, {"parent_session_id": "parent-1", "retry_count": 0}),
            (DispatchResultEvent, {"error": None}),
        ],
    )
    def test_event_roundtrip(self, event_cls, extra_args):
        """Event should serialize/deserialize with all fields preserved."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        original = event_cls(
            session_id="sess-1",
            source=source,
            content="Hello",
            timestamp=12345.0,
            **extra_args,
        )

        # Serialize
        data = serialize_event(original)
        assert data["type"] == event_cls.__name__
        assert data["session_id"] == "sess-1"
        assert data["source"] == "platform-telegram:123:456"

        # Deserialize
        restored = deserialize_event(data)
        assert isinstance(restored, event_cls)
        assert restored.session_id == "sess-1"
        assert restored.content == "Hello"
        assert isinstance(restored.source, TelegramEventSource)
        assert restored.source.user_id == "123"

        # Check extra args preserved
        for key, value in extra_args.items():
            assert getattr(restored, key) == value

    def test_event_with_error_roundtrip(self):
        """Events with error field should preserve it."""
        source = AgentEventSource(agent_id="pickle")

        # OutboundEvent with error
        outbound = OutboundEvent(
            session_id="sess-1",
            source=source,
            content="",
            timestamp=12345.0,
            error="Something failed",
        )
        data = serialize_event(outbound)
        assert data["error"] == "Something failed"
        restored = deserialize_event(data)
        assert restored.error == "Something failed"

        # DispatchResultEvent with error
        dispatch_result = DispatchResultEvent(
            session_id="job-1",
            source=source,
            content="",
            timestamp=12345.0,
            error="Task failed",
        )
        data = serialize_event(dispatch_result)
        restored = deserialize_event(data)
        assert restored.error == "Task failed"

    def test_unknown_event_type_raises(self):
        """deserialize_event should reject unknown types."""
        data = {
            "type": "unknown_type",
            "session_id": "sess-1",
            "source": "agent:test",
            "content": "test",
            "timestamp": 12345.0,
        }
        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(data)


class TestEventBaseClass:
    """Tests for Event base class behavior."""

    def test_event_auto_timestamp(self):
        """Event should auto-populate timestamp."""
        import time

        before = time.time()
        event = InboundEvent(
            session_id="s1",
            source=AgentEventSource(agent_id="test"),
            content="hello",
        )
        after = time.time()

        assert before <= event.timestamp <= after

    def test_inbound_event_no_context_field(self):
        """InboundEvent should not have context field after refactor."""
        source = AgentEventSource(agent_id="pickle")
        event = InboundEvent(
            session_id="sess-1",
            source=source,
            content="hello",
        )

        assert not hasattr(event, "context")
        data = serialize_event(event)
        assert "context" not in data
