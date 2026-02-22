# History Chunk Size Design

## Problem

Session chunking in `HistoryStore` currently uses the same `max_history` value that's passed in for LLM context limiting. This conflates two separate concerns:

1. **Chunk file size** - how many messages to store per `.jsonl` file (disk/memory organization)
2. **LLM context limit** - how many messages to send to the LLM (configurable per mode)

Currently, `save_message()` takes a `max_history` parameter used for chunk splitting decisions, but this value is meant for LLM context, not file organization.

## Solution

Add a dedicated `max_history_file_size` config field that controls chunk file size independently of LLM context limits.

- **Chunk size**: Fixed via `max_history_file_size` config (default 500)
- **LLM context limit**: Remains configurable via `chat_max_history` / `job_max_history`

## Changes

### 1. Config - Add `max_history_file_size` field

```python
# src/picklebot/utils/config.py
max_history_file_size: int = Field(default=500, gt=0)
```

### 2. API Schemas - Add to ConfigUpdate

```python
# src/picklebot/api/schemas.py
max_history_file_size: int | None = None
```

### 3. API Router - Add to endpoints

```python
# src/picklebot/api/routers/config.py
# GET: include in response
# PATCH: handle update via set_user()
```

### 4. HistoryStore - Store config value, simplify save_message signature

```python
# src/picklebot/core/history.py
class HistoryStore:
    def __init__(self, base_path: Path, max_history_file_size: int = 500):
        self.base_path = Path(base_path)
        self.max_history_file_size = max_history_file_size
        # ...

    @staticmethod
    def from_config(config: Config) -> "HistoryStore":
        return HistoryStore(
            config.history_path,
            max_history_file_size=config.max_history_file_size
        )

    def save_message(self, session_id: str, message: HistoryMessage) -> None:
        # No max_history parameter - uses self.max_history_file_size
        if current_count >= self.max_history_file_size:
            # create new chunk
```

### 5. Agent - Update save_message calls

Remove `max_history` argument from all `save_message()` calls.

## Files to Modify

| File | Change |
|------|--------|
| `src/picklebot/utils/config.py` | Add `max_history_file_size` field |
| `src/picklebot/api/schemas.py` | Add to `ConfigUpdate` |
| `src/picklebot/api/routers/config.py` | Add to GET/PATCH endpoints |
| `src/picklebot/core/history.py` | Store chunk size, simplify `save_message()` |
| `src/picklebot/core/agent.py` | Update `save_message()` calls |
| `tests/utils/test_config.py` | Add test for new field |
| `tests/core/test_history.py` | Update tests for new signature |

## Out of Scope

- Changing default values for `chat_max_history` or `job_max_history`
- Migration of existing chunk files
