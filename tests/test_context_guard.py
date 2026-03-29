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

    async def test_check_and_compact_under_threshold_no_roll(
        self, session_state, mock_context
    ):
        """Returns same state when under threshold - no session roll."""
        guard = ContextGuard(shared_context=mock_context, token_threshold=10000)

        session_state.messages = [{"role": "user", "content": "Hello"}]

        result = await guard.check_and_compact(session_state)

        # Should return the same state
        assert result is session_state

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
        mock_session.session_id = new_session_id
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
        mock_session.session_id = new_session_id
        mock_agent.new_session = MagicMock(return_value=mock_session)

        with patch.object(
            guard,
            "_build_compacted_messages",
            new_callable=AsyncMock,
            return_value=[{"role": "user", "content": "[Summary]"}],
        ):
            await guard.check_and_compact(session_state)

        # Verify config_source_session_cache was called to update source mapping
        mock_context.routing_table.config_source_session_cache.assert_called_once_with(
            str(session_state.source), new_session_id
        )


class TestSummaryGeneration:
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


class TestCheckAndCompactWithTruncation:
    """Tests for truncation integration in check_and_compact."""

    @pytest.fixture
    def mock_context(self, tmp_path):
        """Create a mock SharedContext with HistoryStore."""
        mock_context = MagicMock()
        mock_context.history_store = HistoryStore(tmp_path / "history")
        mock_context.config = MagicMock()
        mock_context.config.set_runtime = MagicMock()
        mock_context.prompt_builder = MagicMock()
        mock_context.prompt_builder.build = MagicMock(return_value="System prompt")
        mock_context.routing_table = MagicMock()
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

    async def test_truncation_not_applied_when_under_threshold(
        self, mock_context, mock_agent, tmp_path
    ):
        """When under threshold, tool results are NOT truncated."""
        guard = ContextGuard(shared_context=mock_context, token_threshold=100000)
        source = TelegramEventSource(user_id="123", chat_id="456")
        mock_context.history_store.create_session("test-agent", "test-session", source)

        large_content = "x" * 20000
        state = SessionState(
            session_id="test-session",
            agent=mock_agent,
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "tool", "tool_call_id": "tc1", "content": large_content},
            ],
            source=source,
            shared_context=mock_context,
        )

        result = await guard.check_and_compact(state)

        # Should return same state, content NOT truncated
        assert result is state
        assert result.messages[1]["content"] == large_content

    async def test_truncation_applied_when_over_threshold(
        self, mock_context, mock_agent, tmp_path
    ):
        """When over threshold, large tool results ARE truncated."""
        # Use threshold where truncation alone is sufficient (no compaction needed)
        guard = ContextGuard(shared_context=mock_context, token_threshold=2000)
        source = TelegramEventSource(user_id="123", chat_id="456")
        mock_context.history_store.create_session("test-agent", "test-session", source)

        large_content = "x" * 20000
        state = SessionState(
            session_id="test-session",
            agent=mock_agent,
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "tool", "tool_call_id": "tc1", "content": large_content},
            ],
            source=source,
            shared_context=mock_context,
        )

        result = await guard.check_and_compact(state)

        # Content should be truncated
        assert len(result.messages[1]["content"]) < len(large_content)
        assert "[Truncated" in result.messages[1]["content"]

    async def test_truncation_avoids_compaction_if_sufficient(
        self, mock_context, mock_agent, tmp_path
    ):
        """If truncation brings tokens under threshold, no compaction needed."""
        # Use threshold where truncation alone is sufficient (> 1283 tokens after truncation)
        guard = ContextGuard(shared_context=mock_context, token_threshold=2000)
        source = TelegramEventSource(user_id="123", chat_id="456")
        mock_context.history_store.create_session("test-agent", "test-session", source)

        # One large tool result that when truncated will fit
        large_content = "x" * 20000
        state = SessionState(
            session_id="test-session",
            agent=mock_agent,
            messages=[
                {"role": "user", "content": "Hi"},
                {"role": "tool", "tool_call_id": "tc1", "content": large_content},
            ],
            source=source,
            shared_context=mock_context,
        )

        result = await guard.check_and_compact(state)

        # Should NOT have called compact_and_roll (no LLM summary)
        mock_agent.llm.chat.assert_not_called()
        # Same session, just truncated
        assert result.session_id == "test-session"


class TestTruncateLargeToolResults:
    """Tests for _truncate_large_tool_results method."""

    def test_truncate_small_tool_results_unchanged(self):
        """Small tool results are not modified."""
        guard = ContextGuard(shared_context=None, token_threshold=1000)
        messages = [
            {"role": "user", "content": "Check this file"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "tc1", "content": "Small content"},
        ]

        result = guard._truncate_large_tool_results(messages)

        assert result == messages
        assert result[2]["content"] == "Small content"

    def test_truncate_large_tool_result_content(self):
        """Large tool result content is truncated with notice."""
        guard = ContextGuard(shared_context=None, token_threshold=1000)
        large_content = "x" * 20000  # 20k chars
        messages = [
            {"role": "user", "content": "Check this file"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "tc1", "content": large_content},
        ]

        result = guard._truncate_large_tool_results(messages)

        # Should be truncated
        assert len(result[2]["content"]) < len(large_content)
        assert "[truncated" in result[2]["content"].lower()

    def test_truncate_preserves_non_tool_messages(self):
        """Non-tool messages are preserved unchanged."""
        guard = ContextGuard(shared_context=None, token_threshold=1000)
        large_content = "x" * 20000
        messages = [
            {"role": "user", "content": "Important user message"},
            {
                "role": "assistant",
                "content": "Important assistant message",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "tc1", "content": large_content},
        ]

        result = guard._truncate_large_tool_results(messages)

        # Non-tool messages unchanged
        assert result[0]["content"] == "Important user message"
        assert result[1]["content"] == "Important assistant message"
        # Tool message truncated
        assert len(result[2]["content"]) < len(large_content)

    def test_truncate_multiple_large_tool_results(self):
        """Multiple large tool results are all truncated."""
        guard = ContextGuard(shared_context=None, token_threshold=1000)
        large_content_1 = "a" * 15000
        large_content_2 = "b" * 18000
        messages = [
            {"role": "user", "content": "Check files"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    },
                    {
                        "id": "tc2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "tc1", "content": large_content_1},
            {"role": "tool", "tool_call_id": "tc2", "content": large_content_2},
        ]

        result = guard._truncate_large_tool_results(messages)

        assert len(result[2]["content"]) < len(large_content_1)
        assert len(result[3]["content"]) < len(large_content_2)
        assert "[truncated" in result[2]["content"].lower()
        assert "[truncated" in result[3]["content"].lower()

    def test_truncate_shows_original_size_in_notice(self):
        """Truncation notice includes original size."""
        guard = ContextGuard(shared_context=None, token_threshold=1000)
        large_content = "x" * 20000
        messages = [
            {"role": "tool", "tool_call_id": "tc1", "content": large_content},
        ]

        result = guard._truncate_large_tool_results(messages)

        # Should show original size (20000 chars)
        assert "20000" in result[0]["content"]
