"""Tests for SessionState class."""

from unittest.mock import MagicMock

from picklebot.core.session_state import SessionState
from picklebot.messagebus.telegram_bus import TelegramEventSource


class TestSessionStateCreation:
    def test_session_state_creation(self, tmp_path):
        """SessionState can be created with required fields."""
        from picklebot.core.history import HistoryStore

        mock_agent = MagicMock()
        mock_agent.agent_def.id = "test-agent"

        mock_context = MagicMock()
        mock_context.history_store = HistoryStore(tmp_path)

        source = TelegramEventSource(user_id="123", chat_id="456")

        state = SessionState(
            session_id="test-session-id",
            agent=mock_agent,
            messages=[],
            source=source,
            shared_context=mock_context,
        )

        assert state.session_id == "test-session-id"
        assert state.agent is mock_agent
        assert state.messages == []
        assert state.source == source
        assert state.shared_context is mock_context


class TestSessionStatePersistence:
    def test_add_message_persists_to_history(self, tmp_path):
        """add_message should persist to HistoryStore."""
        from picklebot.core.history import HistoryStore

        mock_agent = MagicMock()
        mock_agent.agent_def.id = "test-agent"

        mock_context = MagicMock()
        mock_context.history_store = HistoryStore(tmp_path)

        source = TelegramEventSource(user_id="123", chat_id="456")

        state = SessionState(
            session_id="test-session-id",
            agent=mock_agent,
            messages=[],
            source=source,
            shared_context=mock_context,
        )

        # Create session in history store
        mock_context.history_store.create_session(
            "test-agent", "test-session-id", source
        )

        # Add a message
        state.add_message({"role": "user", "content": "Hello"})

        # Verify persisted
        messages = mock_context.history_store.get_messages("test-session-id")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"

    def test_add_message_appends_to_memory(self, tmp_path):
        """add_message should append to in-memory list."""
        from picklebot.core.history import HistoryStore

        mock_agent = MagicMock()
        mock_context = MagicMock()
        mock_context.history_store = HistoryStore(tmp_path)

        source = TelegramEventSource(user_id="123", chat_id="456")

        state = SessionState(
            session_id="test-session-id",
            agent=mock_agent,
            messages=[],
            source=source,
            shared_context=mock_context,
        )

        mock_context.history_store.create_session(
            "test-agent", "test-session-id", source
        )

        state.add_message({"role": "user", "content": "Hello"})
        state.add_message({"role": "assistant", "content": "Hi"})

        assert len(state.messages) == 2
        assert state.messages[0]["content"] == "Hello"
        assert state.messages[1]["content"] == "Hi"
