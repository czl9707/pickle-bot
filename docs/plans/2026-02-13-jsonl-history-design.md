# Design: Simplify History Storage with JSONL

## Context

The current `HistoryStore` implementation has unnecessary complexity:
- Three Pydantic models that are often converted to/from dicts anyway
- Dual writes to both session file AND index file for every message
- Manual `.isoformat()` calls scattered throughout
- Index cache adds complexity for marginal benefit
- `aiofiles` dependency for async file operations

This plan simplifies to append-only JSONL format with lightweight Pydantic validation.

## File Structure

```
~/.pickle-bot/history/
├── index.jsonl              # Append-only session metadata
└── sessions/
    └── session-{id}.jsonl   # Append-only messages
```

## Changes

### 1. Simplified Models

Keep two models for validation/type hints:

```python
class HistorySession(BaseModel):
    id: str
    agent_id: str
    title: str | None = None
    message_count: int = 0
    created_at: str  # ISO format string
    updated_at: str  # ISO format string

class HistoryMessage(BaseModel):
    timestamp: str  # ISO format string
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
```

**Removed:** `HistoryIndex` wrapper model, datetime fields (use ISO strings)

### 2. HistoryStore Methods

| Method | Implementation |
|--------|---------------|
| `create_session` | Append entry to index.jsonl, touch session file |
| `save_message` | Append line to session.jsonl, rewrite index with updated count/title |
| `update_session_title` | Rewrite index with updated title |
| `list_sessions` | Read all index.jsonl lines, parse as `HistorySession` |
| `get_messages` | Read all session.jsonl lines, parse as `HistoryMessage` |

### 3. Helper Functions

```python
def _now_iso() -> str:
    return datetime.now().isoformat()
```

### 4. Removed

- `aiofiles` dependency → sync `open()`
- `HistoryIndex` wrapper model
- `_index_cache`
- Dual metadata storage (session file no longer stores metadata)

## File to Modify

- `src/picklebot/core/history.py` - Rewrite entirely

## Verification

1. Run existing tests: `uv run pytest`
2. Manual test: Start chat session, verify history files are created in JSONL format
3. Verify index.jsonl contains session metadata with correct counts
4. Verify session-{id}.jsonl contains one message per line
