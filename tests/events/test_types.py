# tests/events/test_types.py
import pytest

from picklebot.core.events import (
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    Source,
    serialize_event,
    deserialize_event,
)
from picklebot.messagebus.telegram_bus import TelegramContext


class TestInboundEvent:
    """Tests for InboundEvent."""

    def test_inbound_event_creation(self):
        ctx = TelegramContext(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="telegram:123",
            content="Hello",
            timestamp=12345.0,
            retry_count=0,
            context=ctx,
        )
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert event.source == "telegram:123"
        assert event.content == "Hello"
        assert event.timestamp == 12345.0
        assert event.retry_count == 0
        assert event.context == ctx

    def test_inbound_event_defaults(self):
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="cli:cli-user",
            content="Hi",
            timestamp=12345.0,
        )
        assert event.retry_count == 0
        assert event.context is None

    def test_inbound_event_to_dict(self):
        ctx = TelegramContext(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="telegram:123",
            content="Hello",
            timestamp=12345.0,
            context=ctx,
        )
        result = event.to_dict()
        assert result["type"] == "InboundEvent"
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "pickle"
        assert result["context"]["type"] == "TelegramContext"

    def test_inbound_event_from_dict(self):
        data = {
            "type": "InboundEvent",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "telegram:123",
            "content": "Hello",
            "timestamp": 12345.0,
            "retry_count": 1,
            "context": {
                "type": "TelegramContext",
                "data": {"user_id": "123", "chat_id": "456"},
            },
        }
        event = InboundEvent.from_dict(data)
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert isinstance(event.context, TelegramContext)
        assert event.context.chat_id == "456"


class TestOutboundEvent:
    """Tests for OutboundEvent."""

    def test_outbound_event_creation(self):
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="agent:pickle",
            content="Response",
            timestamp=12345.0,
        )
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert event.error is None

    def test_outbound_event_with_error(self):
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="agent:pickle",
            content="",
            timestamp=12345.0,
            error="Something failed",
        )
        assert event.error == "Something failed"

    def test_outbound_event_serialization(self):
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="agent:pickle",
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
        event = DispatchEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:pickle",
            content="Remember this",
            timestamp=12345.0,
            retry_count=0,
            parent_session_id="parent-sess-1",
        )
        assert event.session_id == "job-1"
        assert event.agent_id == "cookie"
        assert event.parent_session_id == "parent-sess-1"

    def test_dispatch_event_serialization(self):
        event = DispatchEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:pickle",
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
        event = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:cookie",
            content="Done",
            timestamp=12345.0,
        )
        assert event.session_id == "job-1"
        assert event.error is None

    def test_dispatch_result_event_with_error(self):
        event = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:cookie",
            content="",
            timestamp=12345.0,
            error="Failed",
        )
        assert event.error == "Failed"


class TestSource:
    """Tests for Source factory methods."""

    def test_source_agent(self):
        assert Source.agent("pickle") == "agent:pickle"

    def test_source_platform(self):
        assert Source.platform("telegram", "user_123") == "telegram:user_123"

    def test_source_cron(self):
        assert Source.cron("daily") == "cron:daily"


class TestEventSerialization:
    """Tests for serialize/deserialize_event helpers."""

    def test_serialize_inbound_event(self):
        ctx = TelegramContext(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="telegram:123",
            content="Hello",
            timestamp=12345.0,
            context=ctx,
        )
        data = serialize_event(event)
        assert data["type"] == "InboundEvent"

    def test_deserialize_inbound_event(self):
        data = {
            "type": "InboundEvent",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "telegram:123",
            "content": "Hello",
            "timestamp": 12345.0,
            "context": {
                "type": "TelegramContext",
                "data": {"user_id": "123", "chat_id": "456"},
            },
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)
        assert event.agent_id == "pickle"

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
            "source": "test",
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
            "source": "test",
            "content": "hello",
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)

        # Should fail with old enum value
        old_data = {
            "type": "inbound",  # Old enum value, not class name
            "session_id": "s1",
            "agent_id": "a1",
            "source": "test",
            "content": "hello",
        }
        with pytest.raises(ValueError, match="Unknown event type"):
            deserialize_event(old_data)
