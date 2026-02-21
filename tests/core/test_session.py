"""Tests for AgentSession."""

from picklebot.core.agent import SessionMode


def test_session_add_message(test_agent):
    """Session should add message to in-memory list and persist to history."""
    session = test_agent.new_session(SessionMode.CHAT)

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = test_agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(test_agent):
    """Session should limit history to max_messages."""
    session = test_agent.new_session(SessionMode.CHAT)

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages


def test_session_get_history_uses_max_history(test_agent):
    """Session should use max_history when max_messages not provided."""
    session = test_agent.new_session(SessionMode.CHAT)
    # chat_max_history default is 50, so add more than that
    for i in range(60):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history()

    assert len(history) == 50
    assert history[0]["content"] == "Message 10"  # Last 50 messages
