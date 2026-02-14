# Message Conversion Methods Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `to_message()` and `from_message()` conversion methods to HistoryMessage class to eliminate duplicated conversion logic.

**Architecture:** Add two methods to the existing HistoryMessage Pydantic model in `core/history.py`. `to_message()` as instance method converts to litellm Message format. `from_message()` as class method creates HistoryMessage from Message. Smart reconstruction handles tool_calls and tool_call_id based on role.

**Tech Stack:** Pydantic v2, litellm types, pathlib

---

## Task 1: Add Test for from_message() with Simple User Message

**Files:**
- Create: `tests/core/test_history.py`

**Step 1: Create test file with imports and first test**

```python
"""Tests for message conversion methods."""

from picklebot.core.history import HistoryMessage


class TestFromMessage:
    """Tests for HistoryMessage.from_message() class method."""

    def test_from_message_simple_user(self):
        """Convert simple user message without optional fields."""
        message = {"role": "user", "content": "Hello, world!"}

        history_msg = HistoryMessage.from_message(message)

        assert history_msg.role == "user"
        assert history_msg.content == "Hello, world!"
        assert history_msg.tool_calls is None
        assert history_msg.tool_call_id is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestFromMessage::test_from_message_simple_user -v`
Expected: FAIL with AttributeError: type object 'HistoryMessage' has no attribute 'from_message'

**Step 3: Commit**

```bash
git add tests/core/test_history.py
git commit -m "test: add test for from_message with simple user message"
```

---

## Task 2: Implement from_message() Class Method

**Files:**
- Modify: `src/picklebot/core/history.py:28-36`

**Step 1: Add imports for litellm types**

At the top of `src/picklebot/core/history.py`, add to imports:

```python
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from litellm.types.completion import ChatCompletionMessageParam as Message  # Add this

from picklebot.utils.config import Config
```

**Step 2: Add from_message() method to HistoryMessage class**

Add this method after the field definitions (around line 36):

```python
@classmethod
def from_message(cls, message: Message) -> "HistoryMessage":
    """
    Create HistoryMessage from litellm Message format.

    Args:
        message: Message dict from litellm

    Returns:
        New HistoryMessage instance
    """
    # Extract tool_calls from assistant messages
    tool_calls = None
    if message.get("tool_calls"):
        tool_calls = [
            {
                "id": tc.get("id"),
                "type": tc.get("type", "function"),
                "function": tc.get("function", {}),
            }
            for tc in message["tool_calls"]
        ]

    # Extract tool_call_id from tool messages
    tool_call_id = message.get("tool_call_id")

    return cls(
        role=message["role"],
        content=str(message.get("content", "")),
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
    )
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestFromMessage::test_from_message_simple_user -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/core/history.py
git commit -m "feat(history): add from_message() class method"
```

---

## Task 3: Add Tests for from_message() with Assistant + Tool Calls

**Files:**
- Modify: `tests/core/test_history.py`

**Step 1: Add test for assistant message with tool calls**

Add to the `TestFromMessage` class:

```python
def test_from_message_assistant_with_tool_calls(self):
    """Convert assistant message with tool calls."""
    message = {
        "role": "assistant",
        "content": "I'll help you with that.",
        "tool_calls": [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "Seattle"}'
                }
            }
        ]
    }

    history_msg = HistoryMessage.from_message(message)

    assert history_msg.role == "assistant"
    assert history_msg.content == "I'll help you with that."
    assert history_msg.tool_calls is not None
    assert len(history_msg.tool_calls) == 1
    assert history_msg.tool_calls[0]["id"] == "call_abc123"
    assert history_msg.tool_calls[0]["function"]["name"] == "get_weather"
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestFromMessage::test_from_message_assistant_with_tool_calls -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/core/test_history.py
git commit -m "test: add test for from_message with assistant and tool calls"
```

---

## Task 4: Add Tests for from_message() with Tool Response

**Files:**
- Modify: `tests/core/test_history.py`

**Step 1: Add test for tool response message**

Add to the `TestFromMessage` class:

```python
def test_from_message_tool_response(self):
    """Convert tool response message."""
    message = {
        "role": "tool",
        "content": "Temperature: 72°F, Sunny",
        "tool_call_id": "call_abc123"
    }

    history_msg = HistoryMessage.from_message(message)

    assert history_msg.role == "tool"
    assert history_msg.content == "Temperature: 72°F, Sunny"
    assert history_msg.tool_call_id == "call_abc123"
    assert history_msg.tool_calls is None
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestFromMessage::test_from_message_tool_response -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/core/test_history.py
git commit -m "test: add test for from_message with tool response"
```

---

## Task 5: Add Tests for to_message() Method

**Files:**
- Modify: `tests/core/test_history.py`

**Step 1: Add test class for to_message()**

Add after the `TestFromMessage` class:

```python
class TestToMessage:
    """Tests for HistoryMessage.to_message() instance method."""

    def test_to_message_simple_user(self):
        """Convert simple user message to Message format."""
        history_msg = HistoryMessage(
            role="user",
            content="Hello!"
        )

        message = history_msg.to_message()

        assert message["role"] == "user"
        assert message["content"] == "Hello!"
        assert "tool_calls" not in message
        assert "tool_call_id" not in message

    def test_to_message_assistant_with_tool_calls(self):
        """Convert assistant message with tool calls to Message format."""
        history_msg = HistoryMessage(
            role="assistant",
            content="Processing...",
            tool_calls=[
                {
                    "id": "call_xyz789",
                    "type": "function",
                    "function": {"name": "calculate", "arguments": '{"x": 1}'}
                }
            ]
        )

        message = history_msg.to_message()

        assert message["role"] == "assistant"
        assert message["content"] == "Processing..."
        assert "tool_calls" in message
        assert len(message["tool_calls"]) == 1

    def test_to_message_tool_response(self):
        """Convert tool response to Message format."""
        history_msg = HistoryMessage(
            role="tool",
            content="Result: 42",
            tool_call_id="call_xyz789"
        )

        message = history_msg.to_message()

        assert message["role"] == "tool"
        assert message["content"] == "Result: 42"
        assert "tool_call_id" in message
        assert message["tool_call_id"] == "call_xyz789"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_history.py::TestToMessage -v`
Expected: FAIL with AttributeError: 'HistoryMessage' object has no attribute 'to_message'

**Step 3: Commit**

```bash
git add tests/core/test_history.py
git commit -m "test: add tests for to_message method"
```

---

## Task 6: Implement to_message() Instance Method

**Files:**
- Modify: `src/picklebot/core/history.py:38-54`

**Step 1: Add to_message() method to HistoryMessage class**

Add this method after the `from_message()` method:

```python
def to_message(self) -> Message:
    """
    Convert HistoryMessage to litellm Message format.

    Returns:
        Message dict compatible with litellm
    """
    base: Message = {
        "role": self.role,
        "content": self.content,
    }

    # Add tool_calls for assistant messages
    if self.role == "assistant" and self.tool_calls:
        base["tool_calls"] = self.tool_calls

    # Add tool_call_id for tool messages
    if self.role == "tool" and self.tool_call_id:
        base["tool_call_id"] = self.tool_call_id

    return base
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_history.py::TestToMessage -v`
Expected: PASS (all 3 tests)

**Step 3: Commit**

```bash
git add src/picklebot/core/history.py
git commit -m "feat(history): add to_message() instance method"
```

---

## Task 7: Add Round-Trip Conversion Test

**Files:**
- Modify: `tests/core/test_history.py`

**Step 1: Add test class for round-trip conversion**

Add after the `TestToMessage` class:

```python
class TestRoundTripConversion:
    """Tests for bidirectional conversion consistency."""

    def test_round_trip_simple_user(self):
        """Verify user message survives round-trip conversion."""
        original = {"role": "user", "content": "Test message"}

        # Message -> HistoryMessage -> Message
        history_msg = HistoryMessage.from_message(original)
        result = history_msg.to_message()

        assert result["role"] == original["role"]
        assert result["content"] == original["content"]

    def test_round_trip_assistant_with_tools(self):
        """Verify assistant message with tools survives round-trip."""
        original = {
            "role": "assistant",
            "content": "Response",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "test", "arguments": "{}"}
                }
            ]
        }

        history_msg = HistoryMessage.from_message(original)
        result = history_msg.to_message()

        assert result["role"] == original["role"]
        assert result["content"] == original["content"]
        assert result["tool_calls"] == original["tool_calls"]

    def test_round_trip_tool_response(self):
        """Verify tool response survives round-trip conversion."""
        original = {
            "role": "tool",
            "content": "Tool output",
            "tool_call_id": "call_456"
        }

        history_msg = HistoryMessage.from_message(original)
        result = history_msg.to_message()

        assert result["role"] == original["role"]
        assert result["content"] == original["content"]
        assert result["tool_call_id"] == original["tool_call_id"]
```

**Step 2: Run all conversion tests**

Run: `uv run pytest tests/core/test_history.py -v`
Expected: PASS (all 9 tests)

**Step 3: Commit**

```bash
git add tests/core/test_history.py
git commit -m "test: add round-trip conversion tests"
```

---

## Task 8: Refactor AgentSession._persist_message()

**Files:**
- Modify: `src/picklebot/core/agent.py:108-133`

**Step 1: Simplify _persist_message() method**

Replace the entire `_persist_message()` method with:

```python
def _persist_message(self, message: Message) -> None:
    """Save to HistoryStore."""
    history_msg = HistoryMessage.from_message(message)
    self.context.history_store.save_message(self.session_id, history_msg)
```

**Step 2: Remove unused imports**

Remove these imports from the top of `src/picklebot/core/agent.py` (if they're now unused):
- `from typing import TYPE_CHECKING, cast` (can remove `cast`, keep `TYPE_CHECKING`)
- `ChatCompletionAssistantMessageParam` (from litellm imports)
- `ChatCompletionToolMessageParam` (from litellm imports)

The litellm imports should become:

```python
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionMessageToolCallParam,
)
```

**Step 3: Run tests to verify nothing broke**

Run: `uv run pytest -v`
Expected: PASS (all tests)

**Step 4: Commit**

```bash
git add src/picklebot/core/agent.py
git commit -m "refactor(agent): use HistoryMessage.from_message() in _persist_message"
```

---

## Task 9: Run Full Test Suite and Lint

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run linters**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address lint issues from message conversion refactor"
```

---

## Summary

**What was built:**
- `HistoryMessage.from_message()` class method for Message → HistoryMessage conversion
- `HistoryMessage.to_message()` instance method for HistoryMessage → Message conversion
- Comprehensive test coverage for all conversion scenarios
- Refactored `AgentSession._persist_message()` to use new methods (25+ lines → 2 lines)

**Benefits:**
- Eliminated duplicated conversion logic
- Removed complex type casting with `cast()`
- Made conversion logic reusable and testable
- Cleaner, more maintainable codebase

**Testing:**
- 9 new tests covering all message types and round-trip conversions
- All existing tests continue to pass
- Full type safety verified with mypy
