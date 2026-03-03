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
