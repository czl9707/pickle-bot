"""Tests for AgentSession."""


def test_session_creation(test_agent):
    """Session should be created with required fields including agent."""
    session = test_agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == test_agent.agent_def.id
    assert session.agent is test_agent
    assert session.messages == []


def test_session_add_message(test_agent):
    """Session should add message to in-memory list and persist to history."""
    session = test_agent.new_session()

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = test_agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(test_agent):
    """Session should limit history to max_messages."""
    session = test_agent.new_session()

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages
