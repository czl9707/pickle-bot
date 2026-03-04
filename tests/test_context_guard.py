# tests/test_context_guard.py
"""Tests for ContextGuard."""

from unittest.mock import MagicMock, patch

from picklebot.core.context_guard import ContextGuard


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
        count = guard.count_tokens([], "gpt-4")
        assert count == 0

    def test_count_tokens_with_messages(self):
        """Count tokens returns positive count for messages."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)
        messages = [{"role": "user", "content": "Hello, world!"}]
        count = guard.count_tokens(messages, "gpt-4")
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


class TestCompactedMessagesBuilder:
    def test_build_compacted_messages(self):
        """Build compacted message list with summary + recent messages."""
        from picklebot.core.context_guard import ContextGuard

        guard = ContextGuard(shared_context=None, token_threshold=1000)

        # 10 messages
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]

        summary = "This is a summary of the conversation."
        result = guard._build_compacted_messages(summary, messages)

        # Should have: summary user + summary assistant + kept recent messages
        assert result[0]["role"] == "user"
        assert "[Previous conversation summary]" in result[0]["content"]
        assert summary in result[0]["content"]

        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Understood, I have the context."

        # Recent messages should be preserved
        assert len(result) > 2


class TestCheckAndCompact:
    def test_check_and_compact_under_threshold(self):
        """Returns messages unchanged when under threshold."""
        guard = ContextGuard(shared_context=None, token_threshold=10000)

        # Mock session
        session = MagicMock()
        session.agent.llm.model = "gpt-4"

        messages = [{"role": "user", "content": "Hello"}]

        result = guard.check_and_compact(session, messages)

        # Should return same messages (under threshold)
        assert result == messages

    def test_check_and_compact_over_threshold_triggers_compaction(self):
        """Triggers compaction when over threshold."""
        # Mock context
        mock_context = MagicMock()
        mock_context.config.set_runtime = MagicMock()

        guard = ContextGuard(
            shared_context=mock_context, token_threshold=10
        )  # Very low threshold

        # Mock session
        session = MagicMock()
        session.agent.llm.model = "gpt-4"
        session.agent.new_session.return_value = MagicMock(session_id="new-session-id")
        session.source = "test:user"

        # Many messages to exceed threshold
        messages = [
            {"role": "user", "content": f"Message {i} " * 100} for i in range(20)
        ]

        with patch.object(guard, "_generate_summary", return_value="Summary"):
            result = guard.check_and_compact(session, messages)

        # Should return compacted messages
        assert len(result) < len(messages)
        assert result[0]["role"] == "user"
        assert "[Previous conversation summary]" in result[0]["content"]
