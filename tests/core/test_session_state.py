"""Tests for SessionState class."""

from unittest.mock import MagicMock

import pytest

from picklebot.core.session_state import SessionState
from picklebot.channel.telegram_channel import TelegramEventSource


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
    @pytest.mark.parametrize(
        "messages_to_add,verify_type",
        [
            ([{"role": "user", "content": "Hello"}], "history"),
            (
                [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"},
                ],
                "memory",
            ),
        ],
        ids=["persist_to_history", "append_to_memory"],
    )
    def test_add_message_behavior(self, tmp_path, messages_to_add, verify_type):
        """add_message should persist to history and append to in-memory list."""
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

        mock_context.history_store.create_session(
            "test-agent", "test-session-id", source
        )

        for msg in messages_to_add:
            state.add_message(msg)

        if verify_type == "history":
            messages = mock_context.history_store.get_messages("test-session-id")
            assert len(messages) == 1
            assert messages[0].role == "user"
            assert messages[0].content == "Hello"
        else:
            assert len(state.messages) == 2
            assert state.messages[0]["content"] == "Hello"
            assert state.messages[1]["content"] == "Hi"
