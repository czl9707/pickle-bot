# Design: Add Message Conversion Methods to HistoryMessage

## Problem

Converting between `HistoryMessage` (persistence format) and `Message` (litellm format for LLM calls) requires duplicated logic with manual type casting. The conversion happens in multiple places:

- `AgentSession._persist_message()` converts `Message` → `HistoryMessage` with 25+ lines of logic
- Loading messages from history would need `HistoryMessage` → `Message` conversion

This leads to:
- Duplicated conversion logic
- Complex type casting with `cast()`
- Harder to test conversion logic in isolation

## Solution

Add two conversion methods to the `HistoryMessage` Pydantic model:
1. `to_message()` - Convert HistoryMessage to litellm Message format
2. `from_message()` - Create HistoryMessage from litellm Message format

## Design

### Method Signatures

**Location:** `src/picklebot/core/history.py` - inside the `HistoryMessage` class

```python
class HistoryMessage(BaseModel):
    """Single message - stored in session.jsonl."""

    timestamp: str = Field(default_factory=_now_iso)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_message(self) -> Message:
        """Convert HistoryMessage to litellm Message format."""

    @classmethod
    def from_message(cls, message: Message) -> "HistoryMessage":
        """Create HistoryMessage from litellm Message format."""
```

### Conversion Logic

**`to_message()` - Smart reconstruction:**
- Returns base message dict with `role` and `content`
- Adds `tool_calls` field for assistant messages (when present)
- Adds `tool_call_id` field for tool messages (when present)

**`from_message()` - Extraction with casting:**
- Extracts `tool_calls` from assistant messages with proper structure
- Extracts `tool_call_id` from tool messages
- Converts `content` to string for safety
- Handles all message roles (user, assistant, system, tool)

### Usage Examples

**Before refactoring:**
```python
def _persist_message(self, message: Message) -> None:
    """Save to HistoryStore."""
    tool_calls = None
    if message.get("tool_calls", None):
        message = cast(ChatCompletionAssistantMessageParam, message)
        tool_calls = [
            {
                "id": tc.get("id"),
                "type": tc.get("type", "function"),
                "function": tc.get("function", {}),
            }
            for tc in message.get("tool_calls", [])
        ]

    tool_call_id = None
    if message.get("tool_call_id", None):
        message = cast(ChatCompletionToolMessageParam, message)
        tool_call_id = message.get("tool_call_id")

    history_msg = HistoryMessage(
        role=message["role"],  # type: ignore
        content=str(message.get("content", "")),
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
    )
    self.context.history_store.save_message(self.session_id, history_msg)
```

**After refactoring:**
```python
def _persist_message(self, message: Message) -> None:
    """Save to HistoryStore."""
    history_msg = HistoryMessage.from_message(message)
    self.context.history_store.save_message(self.session_id, history_msg)
```

**Loading from history:**
```python
# Load and convert for LLM context
history_messages = self.context.history_store.get_messages(session_id)
messages = [msg.to_message() for msg in history_messages]
```

## Benefits

- **Reduces code:** 25+ lines reduced to 2 lines in `_persist_message()`
- **Removes type casting:** No more `cast()` calls
- **Reusability:** Conversion logic available wherever needed
- **Testability:** Isolated conversion logic easy to test
- **Maintainability:** Single source of truth for message format conversions

## Testing Strategy

**Test file:** `tests/core/test_history.py`

**Test cases:**
1. `from_message()` with different message types:
   - Simple user message
   - Assistant message with tool_calls
   - Tool message with tool_call_id
   - System message

2. `to_message()` with different history message types:
   - User message (no optional fields)
   - Assistant message with tool_calls
   - Tool message with tool_call_id

3. Round-trip conversion:
   - Message → HistoryMessage → Message preserves data

## Implementation Order

1. Add test cases for conversion methods
2. Implement `to_message()` method
3. Implement `from_message()` method
4. Run tests to verify conversion logic
5. Refactor `AgentSession._persist_message()` to use `from_message()`
6. Run full test suite to ensure no regressions
7. Run linters (ruff, mypy) to verify type safety
