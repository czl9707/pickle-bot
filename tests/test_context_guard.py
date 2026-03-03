# tests/test_context_guard.py
"""Tests for ContextGuard."""

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
