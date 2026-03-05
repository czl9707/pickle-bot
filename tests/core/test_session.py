"""Tests for AgentSession."""

from picklebot.messagebus.telegram_bus import TelegramEventSource


def test_session_add_message(test_agent):
    """Session should add message to in-memory list and persist to history."""
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = test_agent.new_session(source=source)

    session.state.add_message({"role": "user", "content": "Hello"})

    assert len(session.state.messages) == 1
    assert session.state.messages[0]["role"] == "user"

    # Verify persisted - Agent has context, AgentSession has shared_context
    messages = test_agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_returns_all_messages(test_agent):
    """Session.get_history should return all messages (token limiting is handled by ContextGuard)."""
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = test_agent.new_session(source=source)

    # Add 5 messages
    for i in range(5):
        session.state.add_message({"role": "user", "content": f"Message {i}"})

    history = session.state.messages

    # get_history returns all messages - token limiting is handled by ContextGuard
    assert len(history) == 5
    assert history[0]["content"] == "Message 0"
    assert history[4]["content"] == "Message 4"
