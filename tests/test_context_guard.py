# tests/test_context_guard.py
"""Tests for ContextGuard."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from picklebot.core.context_guard import ContextGuard
from picklebot.core.session_state import SessionState
from picklebot.core.history import HistoryStore
from picklebot.channel.telegram_channel import TelegramEventSource


class TestContextGuard:
    def test_context_guard_exists(self):
        """ContextGuard can be instantiated."""
        guard = ContextGuard(shared_context=None, token_threshold=1000)
        assert guard.token_threshold == 1000


class TestTokenCounting:
    def test_count_tokens_empty_messages(self):
        """Count tokens returns 0 for empty messages."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)
        count = guard._count_tokens([], "gpt-4")
        assert count == 0

    def test_count_tokens_with_messages(self):
        """Count tokens returns positive count for messages."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)
        messages = [{"role": "user", "content": "Hello, world!"}]
        count = guard._count_tokens(messages, "gpt-4")
        assert count > 0


class TestMessageSerialization:
    def test_serialize_messages_for_summary(self):
        """Serialize messages to plain text for summarization."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = guard._serialize_messages_for_summary(messages)

        assert "USER:" in result
        assert "Hello" in result
        assert "ASSISTANT:" in result
        assert "Hi there!" in result

    def test_serialize_messages_with_tool_calls(self):
        """Serialize assistant messages with tool calls."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)
        messages = [
            {
                "role": "assistant",
                "content": "Let me check that.",
                "tool_calls": [
                    {
                        "function": {
                            "name": "web_search",
                            "arguments": "{}",
                        }
                    },
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": "{}",
                        }
                    },
                ],
            }
        ]
        result = guard._serialize_messages_for_summary(messages)

        assert "ASSISTANT:" in result
        assert "Let me check that." in result
        assert "[used tools:" in result
        assert "web_search" in result
        assert "read_file" in result


class TestCheckAndCompactWithSessionState:
    """Tests for the new SessionState-based check_and_compact signature."""

    @pytest.fixture
    def mock_context(self, tmp_path):
        """Create a mock SharedContext with HistoryStore."""
        mock_context = MagicMock()
        mock_context.history_store = HistoryStore(tmp_path / "history")
        mock_context.config = MagicMock()
        mock_context.config.set_runtime = MagicMock()
        mock_context.prompt_builder = MagicMock()
        mock_context.prompt_builder.build = MagicMock(return_value="System prompt")
        return mock_context

    @pytest.fixture
    def mock_agent(self):
        """Create a mock Agent."""
        mock_agent = MagicMock()
        mock_agent.agent_def.id = "test-agent"
        mock_agent.agent_def.agent_md = "You are a test assistant."
        mock_agent.agent_def.soul_md = None
        mock_agent.llm.model = "gpt-4"
        mock_agent.llm.chat = AsyncMock(return_value=("Summary text", []))
        return mock_agent

    @pytest.fixture
    def session_state(self, mock_agent, mock_context, tmp_path):
        """Create a SessionState for testing."""
        source = TelegramEventSource(user_id="123", chat_id="456")

        # Create the session in history store
        mock_context.history_store.create_session(
            "test-agent", "test-session-id", source
        )

        state = SessionState(
            session_id="test-session-id",
            agent=mock_agent,
            messages=[],
            source=source,
            shared_context=mock_context,
        )
        return state

    @pytest.mark.asyncio
    async def test_check_and_compact_returns_state(self, session_state):
        """check_and_compact returns SessionState (same or new)."""
        guard = ContextGuard(shared_context=None, token_threshold=10000)

        # Add a small message
        session_state.messages = [{"role": "user", "content": "Hello"}]

        result = await guard.check_and_compact(session_state)

        # Should return SessionState
        assert isinstance(result, SessionState)
        # Under threshold, should return same state
        assert result is session_state

    @pytest.mark.asyncio
    async def test_check_and_compact_under_threshold_no_roll(
        self, session_state, mock_context
    ):
        """Returns same state when under threshold - no session roll."""
        guard = ContextGuard(shared_context=mock_context, token_threshold=10000)

        session_state.messages = [{"role": "user", "content": "Hello"}]

        result = await guard.check_and_compact(session_state)

        # Should return the same state
        assert result is session_state

    @pytest.mark.asyncio
    async def test_check_and_compact_over_threshold_triggers_roll(
        self, session_state, mock_context, mock_agent
    ):
        """Returns new SessionState when over threshold - session rolls."""
        guard = ContextGuard(shared_context=mock_context, token_threshold=10)

        # Many messages to exceed threshold
        session_state.messages = [
            {"role": "user", "content": f"Message {i} " * 100} for i in range(20)
        ]

        # Mock new_session to return a session with a new SessionState
        new_session_id = "new-session-id"

        # Create the new session in history store first
        mock_context.history_store.create_session(
            "test-agent", new_session_id, session_state.source
        )

        new_state = SessionState(
            session_id=new_session_id,
            agent=mock_agent,
            messages=[],
            source=session_state.source,
            shared_context=mock_context,
        )
        mock_session = MagicMock()
        mock_session.state = new_state
        mock_session.session_id = new_session_id
        mock_agent.new_session = MagicMock(return_value=mock_session)

        with patch.object(
            guard,
            "_build_compacted_messages",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": "[Summary]"}],
        ):
            result_state = await guard.check_and_compact(session_state)

        # Should return new SessionState
        assert result_state is not None
        assert isinstance(result_state, SessionState)
        assert result_state.session_id == new_session_id
        assert result_state.session_id != session_state.session_id
        assert result_state.agent is mock_agent
        assert result_state.source == session_state.source

    @pytest.mark.asyncio
    async def test_roll_creates_new_session_in_history_store(
        self, session_state, mock_context, mock_agent
    ):
        """Rolling creates a new session in HistoryStore."""
        guard = ContextGuard(shared_context=mock_context, token_threshold=10)

        session_state.messages = [
            {"role": "user", "content": f"Message {i} " * 100} for i in range(20)
        ]

        # Mock new_session
        new_session_id = "new-session-id"
        mock_context.history_store.create_session(
            "test-agent", new_session_id, session_state.source
        )
        new_state = SessionState(
            session_id=new_session_id,
            agent=mock_agent,
            messages=[],
            source=session_state.source,
            shared_context=mock_context,
        )
        mock_session = MagicMock()
        mock_session.state = new_state
        mock_agent.new_session = MagicMock(return_value=mock_session)

        with patch.object(
            guard,
            "_build_compacted_messages",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": "[Summary]"}],
        ):
            result_state = await guard.check_and_compact(session_state)

        # Verify new session was created in history store
        assert result_state is not None
        sessions = mock_context.history_store.list_sessions()
        session_ids = [s.id for s in sessions]
        assert result_state.session_id in session_ids

    @pytest.mark.asyncio
    async def test_roll_updates_source_mapping(
        self, session_state, mock_context, mock_agent
    ):
        """Rolling updates the source -> session_id mapping."""
        guard = ContextGuard(shared_context=mock_context, token_threshold=10)

        session_state.messages = [
            {"role": "user", "content": f"Message {i} " * 100} for i in range(20)
        ]

        # Mock new_session
        new_session_id = "new-session-id"
        mock_context.history_store.create_session(
            "test-agent", new_session_id, session_state.source
        )
        new_state = SessionState(
            session_id=new_session_id,
            agent=mock_agent,
            messages=[],
            source=session_state.source,
            shared_context=mock_context,
        )
        mock_session = MagicMock()
        mock_session.state = new_state
        mock_agent.new_session = MagicMock(return_value=mock_session)

        with patch.object(
            guard,
            "_build_compacted_messages",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": "[Summary]"}],
        ):
            await guard.check_and_compact(session_state)

        # Verify set_runtime was called to update source mapping
        mock_context.config.set_runtime.assert_called_once()
        call_args = mock_context.config.set_runtime.call_args
        assert call_args[0][0].startswith("sources.")


class TestSummaryGeneration:
    @pytest.mark.asyncio
    async def test_build_compacted_messages(self, tmp_path):
        """Build compacted messages using SessionState."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)

        # Mock agent with LLM
        mock_agent = MagicMock()
        mock_agent.llm.chat = AsyncMock(return_value=("Summary text", []))

        # Mock context
        mock_context = MagicMock()

        # Create SessionState with messages
        source = TelegramEventSource(user_id="123", chat_id="456")
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "Tell me more"},
            {"role": "assistant", "content": "It's high-level and interpreted."},
        ]
        state = SessionState(
            session_id="test-session",
            agent=mock_agent,
            messages=messages,
            source=source,
            shared_context=mock_context,
        )

        result = await guard._build_compacted_messages(state)

        # Should return list of messages
        assert isinstance(result, list)
        assert len(result) > 0
        # First message should be the summary
        assert result[0]["role"] == "user"
        assert "[Previous conversation summary]" in result[0]["content"]
        assert "Summary text" in result[0]["content"]
        mock_agent.llm.chat.assert_called_once()
