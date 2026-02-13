from picklebot.core.session import Session
from picklebot.core.history import HistoryStore


def test_session_creation(tmp_path):
    """Session should be created with required fields."""
    history_store = HistoryStore(tmp_path / "history")
    history_store.create_session("test-agent", "test-session-id")

    session = Session(
        session_id="test-session-id", agent_id="test-agent", history_store=history_store
    )

    assert session.session_id == "test-session-id"
    assert session.agent_id == "test-agent"
    assert session.messages == []


def test_session_add_message(tmp_path):
    """Session should add message to in-memory list and persist to history."""
    history_store = HistoryStore(tmp_path / "history")
    history_store.create_session("test-agent", "test-session-id")

    session = Session(
        session_id="test-session-id", agent_id="test-agent", history_store=history_store
    )

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = history_store.get_messages("test-session-id")
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(tmp_path):
    """Session should limit history to max_messages."""
    history_store = HistoryStore(tmp_path / "history")
    history_store.create_session("test-agent", "test-session-id")

    session = Session(
        session_id="test-session-id", agent_id="test-agent", history_store=history_store
    )

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages
