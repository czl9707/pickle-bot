"""Tests for message conversion methods."""

import json
import tempfile
from pathlib import Path

import pytest

from picklebot.core.history import HistoryStore, HistoryMessage


class TestFromMessage:
    """Tests for HistoryMessage.from_message() class method."""

    def test_from_message_simple_user(self):
        """Convert simple user message without optional fields."""
        message = {"role": "user", "content": "Hello, world!"}

        history_msg = HistoryMessage.from_message(message)

        assert history_msg.role == "user"
        assert history_msg.content == "Hello, world!"
        assert history_msg.tool_calls is None
        assert history_msg.tool_call_id is None

    def test_from_message_assistant_with_tool_calls(self):
        """Convert assistant message with tool calls."""
        message = {
            "role": "assistant",
            "content": "I'll help you with that.",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Seattle"}',
                    },
                }
            ],
        }

        history_msg = HistoryMessage.from_message(message)

        assert history_msg.role == "assistant"
        assert history_msg.content == "I'll help you with that."
        assert history_msg.tool_calls is not None
        assert len(history_msg.tool_calls) == 1
        assert history_msg.tool_calls[0]["id"] == "call_abc123"
        assert history_msg.tool_calls[0]["function"]["name"] == "get_weather"

    def test_from_message_tool_response(self):
        """Convert tool response message."""
        message = {
            "role": "tool",
            "content": "Temperature: 72°F, Sunny",
            "tool_call_id": "call_abc123",
        }

        history_msg = HistoryMessage.from_message(message)

        assert history_msg.role == "tool"
        assert history_msg.content == "Temperature: 72°F, Sunny"
        assert history_msg.tool_call_id == "call_abc123"
        assert history_msg.tool_calls is None


class TestToMessage:
    """Tests for HistoryMessage.to_message() instance method."""

    def test_to_message_simple_user(self):
        """Convert simple user message to Message format."""
        history_msg = HistoryMessage(role="user", content="Hello!")

        message = history_msg.to_message()

        assert message["role"] == "user"
        assert message["content"] == "Hello!"
        assert "tool_calls" not in message
        assert "tool_call_id" not in message

    def test_to_message_assistant_with_tool_calls(self):
        """Convert assistant message with tool calls to Message format."""
        history_msg = HistoryMessage(
            role="assistant",
            content="Processing...",
            tool_calls=[
                {
                    "id": "call_xyz789",
                    "type": "function",
                    "function": {"name": "calculate", "arguments": '{"x": 1}'},
                }
            ],
        )

        message = history_msg.to_message()

        assert message["role"] == "assistant"
        assert message["content"] == "Processing..."
        assert "tool_calls" in message
        assert len(message["tool_calls"]) == 1

    def test_to_message_tool_response(self):
        """Convert tool response to Message format."""
        history_msg = HistoryMessage(
            role="tool", content="Result: 42", tool_call_id="call_xyz789"
        )

        message = history_msg.to_message()

        assert message["role"] == "tool"
        assert message["content"] == "Result: 42"
        assert "tool_call_id" in message
        assert message["tool_call_id"] == "call_xyz789"


class TestRoundTripConversion:
    """Tests for bidirectional conversion consistency."""

    def test_round_trip_simple_user(self):
        """Verify user message survives round-trip conversion."""
        original = {"role": "user", "content": "Test message"}

        # Message -> HistoryMessage -> Message
        history_msg = HistoryMessage.from_message(original)
        result = history_msg.to_message()

        assert result["role"] == original["role"]
        assert result["content"] == original["content"]

    def test_round_trip_assistant_with_tools(self):
        """Verify assistant message with tools survives round-trip."""
        original = {
            "role": "assistant",
            "content": "Response",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "test", "arguments": "{}"},
                }
            ],
        }

        history_msg = HistoryMessage.from_message(original)
        result = history_msg.to_message()

        assert result["role"] == original["role"]
        assert result["content"] == original["content"]
        assert result["tool_calls"] == original["tool_calls"]

    def test_round_trip_tool_response(self):
        """Verify tool response survives round-trip conversion."""
        original = {
            "role": "tool",
            "content": "Tool output",
            "tool_call_id": "call_456",
        }

        history_msg = HistoryMessage.from_message(original)
        result = history_msg.to_message()

        assert result["role"] == original["role"]
        assert result["content"] == original["content"]
        assert result["tool_call_id"] == original["tool_call_id"]


@pytest.fixture
def temp_history_dir():
    """Create a temporary directory for history storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(temp_history_dir):
    """Create a HistoryStore instance."""
    return HistoryStore(temp_history_dir)


class TestHistoryStoreInit:
    def test_creates_directories(self, temp_history_dir):
        """HistoryStore should create required directories."""
        HistoryStore(temp_history_dir)
        assert temp_history_dir.exists()
        assert (temp_history_dir / "sessions").exists()

    def test_index_file_created_on_first_write(self, store):
        """Index file should not exist until first session created."""
        assert not store.index_path.exists()


class TestCreateSession:
    def test_creates_session(self, store):
        """create_session should return session metadata."""
        session = store.create_session("test-agent", "session-123")

        assert session["id"] == "session-123"
        assert session["agent_id"] == "test-agent"
        assert session["title"] is None
        assert session["message_count"] == 0

    def test_creates_index_entry(self, store):
        """create_session should append to index.jsonl."""
        store.create_session("test-agent", "session-123")

        with open(store.index_path) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["id"] == "session-123"

    def test_creates_empty_session_file(self, store):
        """create_session should create empty session file."""
        store.create_session("test-agent", "session-123")

        session_file = store.sessions_path / "session-session-123.jsonl"
        assert session_file.exists()
        with open(session_file) as f:
            content = f.read()
        assert content == ""

    def test_multiple_sessions(self, store):
        """Multiple sessions should be appended to index."""
        store.create_session("agent-1", "session-1")
        store.create_session("agent-2", "session-2")

        sessions = store.list_sessions()
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0].id == "session-2"
        assert sessions[1].id == "session-1"


class TestSaveMessage:
    def test_appends_message_to_session_file(self, store):
        """save_message should append line to session file."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(role="user", content="Hello")
        store.save_message("session-1", msg)

        session_file = store.sessions_path / "session-session-1.jsonl"
        with open(session_file) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["role"] == "user"
        assert entry["content"] == "Hello"

    def test_updates_message_count_in_index(self, store):
        """save_message should update message_count in index."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(role="user", content="Hello")
        store.save_message("session-1", msg)

        sessions = store.list_sessions()
        assert sessions[0].message_count == 1

    def test_auto_generates_title_from_first_user_message(self, store):
        """First user message should auto-generate session title."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(
            role="user",
            content="This is a long question that should definitely be truncated now",
        )
        store.save_message("session-1", msg)

        sessions = store.list_sessions()
        assert (
            sessions[0].title == "This is a long question that should definitely be ..."
        )

    def test_handles_tool_calls(self, store):
        """save_message should store tool_calls."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "call-1", "function": {"name": "test"}}],
        )
        store.save_message("session-1", msg)

        messages = store.get_messages("session-1")
        assert messages[0].tool_calls is not None
        assert messages[0].tool_calls[0]["id"] == "call-1"


class TestGetMessages:
    def test_returns_empty_list_for_new_session(self, store):
        """get_messages should return empty list for new session."""
        store.create_session("agent", "session-1")

        messages = store.get_messages("session-1")
        assert messages == []

    def test_returns_all_messages(self, store):
        """get_messages should return all messages in order."""
        store.create_session("agent", "session-1")

        store.save_message("session-1", HistoryMessage(role="user", content="Hello"))
        store.save_message(
            "session-1", HistoryMessage(role="assistant", content="Hi there")
        )

        messages = store.get_messages("session-1")
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"


class TestUpdateSessionTitle:
    def test_updates_title_in_index(self, store):
        """update_session_title should update title in index."""
        store.create_session("agent", "session-1")

        store.update_session_title("session-1", "New Title")

        sessions = store.list_sessions()
        assert sessions[0].title == "New Title"


class TestListSessions:
    def test_returns_empty_list_when_no_sessions(self, store):
        """list_sessions should return empty list initially."""
        sessions = store.list_sessions()
        assert sessions == []

    def test_returns_sessions_ordered_by_updated_at(self, store):
        """list_sessions should return most recently updated first."""
        store.create_session("agent", "session-1")
        store.create_session("agent", "session-2")

        # Update session-1
        store.save_message("session-1", HistoryMessage(role="user", content="Hi"))

        sessions = store.list_sessions()
        assert sessions[0].id == "session-1"  # Most recently updated
        assert sessions[1].id == "session-2"
