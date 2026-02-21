# Session Chunking Design

## Problem

Sessions in MessageBus context grow indefinitely, causing:

1. **Disk bloat** - single JSONL file grows without bound
2. **Memory bloat** - loading large sessions when resuming

The `max_history` config limits what's sent to the LLM, but doesn't limit what's stored or loaded into memory.

## Solution

Split each session into multiple chunk files internally. Each chunk holds up to `max_history` messages.

- Session ID stays stable (no rotation/notification complexity)
- Only internal file organization changes
- Memory bounded naturally - only load what's needed

## File Structure

**Before:**
```
sessions/
└── session-abc-123.jsonl   # grows forever
```

**After:**
```
sessions/
├── session-abc-123.1.jsonl   # chunk 1 (max_history messages)
├── session-abc-123.2.jsonl   # chunk 2 (max_history messages)
└── session-abc-123.3.jsonl   # chunk 3 (active, < max_history)
```

Naming convention: `session-{id}.{index}.jsonl`

Index always present (even for first chunk) - no special cases.

## Behavior

| Operation | Behavior |
|-----------|----------|
| Create session | Create `session-{id}.1.jsonl` |
| Write message | Append to newest chunk. If chunk has `max_history` messages, create `.{n+1}.jsonl` |
| Read messages | Load from newest chunk(s) backwards until `max_history` messages total |
| Resume session | Same as read - only load `max_history` messages |

## Implementation

### HistoryStore Changes

```python
def _chunk_pattern(self, session_id: str) -> str:
    return f"session-{session_id}.*.jsonl"

def _chunk_path(self, session_id: str, index: int) -> Path:
    return self.sessions_path / f"session-{session_id}.{index}.jsonl"

def _get_current_chunk_index(self, session_id: str) -> int:
    """Scan for existing chunks, return highest index (or 1 if none)."""

def save_message(self, session_id: str, message: HistoryMessage) -> None:
    """Append to current chunk, create new chunk if full."""

def get_messages(self, session_id: str) -> list[HistoryMessage]:
    """Load newest chunks until max_history messages."""
```

### Dependencies

- Needs access to `max_history` config (per session's agent)
- May need to pass `max_history` to `HistoryStore` methods, or store in `HistorySession`

### Optional Optimization

Add `chunk_count: int` to `HistorySession` to avoid filesystem scan when determining current chunk index.

## Migration

No code migration needed (pre-release). Existing session files will be manually renamed:

```
session-abc-123.jsonl → session-abc-123.1.jsonl
```

## Out of Scope

- Deleting/archiving old chunks (can be added later)
- Traversing chunk history beyond `max_history`
- Compression of old chunks
