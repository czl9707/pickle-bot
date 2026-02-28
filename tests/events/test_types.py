# tests/events/test_types.py
from picklebot.events.types import Event, EventType, Source


class TestEvent:
    """Tests for Event creation and serialization."""

    def test_event_creation(self):
        event = Event(
            type=EventType.OUTBOUND,
            session_id="test-session",
            content="Hello world",
            source=Source.agent("pickle"),
            timestamp=12345.0,
            metadata={"agent_id": "pickle"},
        )
        assert event.type == EventType.OUTBOUND
        assert event.session_id == "test-session"
        assert event.content == "Hello world"
        assert event.source == "agent:pickle"
        assert event.timestamp == 12345.0
        assert event.metadata == {"agent_id": "pickle"}

    def test_event_default_metadata(self):
        event = Event(
            type=EventType.INBOUND,
            session_id="test-session",
            content="Hi",
            source=Source.platform("telegram", "user_123"),
            timestamp=12345.0,
        )
        assert event.metadata == {}

    def test_event_to_dict(self):
        event = Event(
            type=EventType.OUTBOUND,
            session_id="test-session",
            content="Hello",
            source=Source.agent("pickle"),
            timestamp=12345.0,
            metadata={"key": "value"},
        )
        result = event.to_dict()
        assert result == {
            "type": "outbound",
            "session_id": "test-session",
            "content": "Hello",
            "source": "agent:pickle",
            "timestamp": 12345.0,
            "metadata": {"key": "value"},
        }

    def test_event_from_dict(self):
        data = {
            "type": "outbound",
            "session_id": "test-session",
            "content": "Hello",
            "source": "agent:pickle",
            "timestamp": 12345.0,
            "metadata": {"key": "value"},
        }
        event = Event.from_dict(data)
        assert event.type == EventType.OUTBOUND
        assert event.session_id == "test-session"
        assert event.content == "Hello"
