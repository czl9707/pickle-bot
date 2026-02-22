# History Chunk Size Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dedicated `max_history_file_size` config to control chunk file size independently of LLM context limits.

**Architecture:** Config gets new field `max_history_file_size` (default 500). HistoryStore stores this value on init and uses it for chunk splitting. The `save_message()` method no longer takes a `max_history` parameter.

**Tech Stack:** Pydantic, FastAPI, pytest

---

## Task 1: Add `max_history_file_size` to Config

**Files:**
- Modify: `src/picklebot/utils/config.py:120-121`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py` in `TestSessionHistoryLimits` class:

```python
def test_config_default_max_history_file_size(self, llm_config):
    """Config should have default max_history_file_size."""
    config = Config(
        workspace=Path("/workspace"),
        llm=llm_config,
        default_agent="test",
    )
    assert config.max_history_file_size == 500

def test_config_custom_max_history_file_size(self, llm_config):
    """Config should allow custom max_history_file_size."""
    config = Config(
        workspace=Path("/workspace"),
        llm=llm_config,
        default_agent="test",
        max_history_file_size=1000,
    )
    assert config.max_history_file_size == 1000

def test_config_max_history_file_size_must_be_positive(self, llm_config):
    """Config should reject non-positive max_history_file_size."""
    with pytest.raises(ValidationError):
        Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
            max_history_file_size=0,
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::TestSessionHistoryLimits -v`
Expected: FAIL - `max_history_file_size` field doesn't exist

**Step 3: Write minimal implementation**

Add to `src/picklebot/utils/config.py` after `job_max_history` (line 121):

```python
max_history_file_size: int = Field(default=500, gt=0)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::TestSessionHistoryLimits -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add max_history_file_size field"
```

---

## Task 2: Add to API schemas

**Files:**
- Modify: `src/picklebot/api/schemas.py:58-59`
- Test: `tests/api/test_schemas.py` (if exists) or skip

**Step 1: Write the failing test**

Check if `tests/api/test_schemas.py` exists. If not, skip test step and go to Step 3.

**Step 2: Run test to verify it fails**

(If test file exists) Run: `uv run pytest tests/api/test_schemas.py -v`

**Step 3: Write minimal implementation**

Add to `src/picklebot/api/schemas.py` in `ConfigUpdate` class after `job_max_history`:

```python
max_history_file_size: int | None = None
```

**Step 4: Run test to verify it passes**

(If test file exists) Run: `uv run pytest tests/api/test_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/api/schemas.py
git commit -m "feat(api): add max_history_file_size to ConfigUpdate schema"
```

---

## Task 3: Add to API router

**Files:**
- Modify: `src/picklebot/api/routers/config.py:17-18, 26-27, 39-41, 45-46`
- Test: Check via manual API test or existing router tests

**Step 1: Write the failing test**

Check if config router tests exist. If not, verify manually after implementation.

**Step 2: Run test to verify it fails**

(If test exists) Run: `uv run pytest tests/api/routers/test_config.py -v`

**Step 3: Write minimal implementation**

1. Add to `ConfigResponse` model (line 17-18):
```python
max_history_file_size: int
```

2. Add to GET response (line 26-27):
```python
"max_history_file_size": ctx.config.max_history_file_size,
```

3. Add to PATCH handler (line 39-41):
```python
if data.max_history_file_size is not None:
    ctx.config.set_user("max_history_file_size", data.max_history_file_size)
```

4. Add to PATCH response (line 45-46):
```python
"max_history_file_size": ctx.config.max_history_file_size,
```

**Step 4: Run test to verify it passes**

(If test exists) Run: `uv run pytest tests/api/routers/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/api/routers/config.py
git commit -m "feat(api): add max_history_file_size to config endpoints"
```

---

## Task 4: Update HistoryStore

**Files:**
- Modify: `src/picklebot/core/history.py:103-128, 206-227`
- Test: `tests/core/test_history.py`

**Step 1: Write the failing test**

Update fixture in `tests/core/test_history.py` to pass `max_history_file_size`:

Find the `history_store` fixture and update it to:
```python
@pytest.fixture
def history_store(tmp_path):
    return HistoryStore(tmp_path / "history", max_history_file_size=3)
```

Then update tests in `TestSaveMessageChunking` to not pass `max_history` parameter:

```python
class TestSaveMessageChunking:
    def test_creates_new_chunk_when_full(self, history_store):
        """save_message should create new chunk when current is full."""
        history_store.create_session("agent", "session-1")

        # Fill first chunk (3 messages = max_history_file_size)
        for i in range(3):
            history_store.save_message(
                "session-1",
                HistoryMessage(role="user", content=f"msg{i}"),
            )

        # Next message should create chunk 2
        history_store.save_message(
            "session-1", HistoryMessage(role="user", content="msg3")
        )

        # ... rest of test unchanged

    def test_updates_chunk_count_in_index(self, history_store):
        """save_message should update chunk_count when creating new chunk."""
        history_store.create_session("agent", "session-1")

        # Fill chunk 1
        history_store.save_message(
            "session-1", HistoryMessage(role="user", content="a")
        )
        history_store.save_message(
            "session-1", HistoryMessage(role="user", content="b")
        )

        # Create chunk 2
        history_store.save_message(
            "session-1", HistoryMessage(role="user", content="c")
        )

        sessions = history_store.list_sessions()
        assert sessions[0].chunk_count == 2

    def test_appends_to_current_chunk_when_not_full(self, history_store):
        """save_message should append to current chunk when not full."""
        history_store.create_session("agent", "session-1")

        history_store.save_message(
            "session-1", HistoryMessage(role="user", content="hello")
        )

        # Should still be on chunk 1
        chunk_count = history_store._count_messages_in_chunk(
            history_store._chunk_path("session-1", 1)
        )
        assert chunk_count == 1
        assert not history_store._chunk_path("session-1", 2).exists()
```

Also update `TestGetMessagesChunking` to use small fixture value:

```python
class TestGetMessagesChunking:
    def test_loads_from_multiple_chunks(self, history_store):
        """get_messages should load from multiple chunks, newest first."""
        history_store.create_session("agent", "session-1")

        # Create 5 messages across 3 chunks (max_history_file_size=3 per chunk)
        for i in range(5):
            history_store.save_message(
                "session-1",
                HistoryMessage(role="user", content=f"msg{i}"),
            )

        # max_history=2, so should only get last 2 messages
        messages = history_store.get_messages("session-1", max_history=2)
        assert len(messages) == 2
        assert messages[0].content == "msg3"
        assert messages[1].content == "msg4"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestSaveMessageChunking -v`
Expected: FAIL - `save_message() got an unexpected keyword argument 'max_history'`

**Step 3: Write minimal implementation**

1. Update `__init__` to accept and store `max_history_file_size`:

```python
def __init__(self, base_path: Path, max_history_file_size: int = 500):
    self.base_path = Path(base_path)
    self.sessions_path = self.base_path / "sessions"
    self.index_path = self.base_path / "index.jsonl"
    self.max_history_file_size = max_history_file_size

    self.base_path.mkdir(parents=True, exist_ok=True)
    self.sessions_path.mkdir(parents=True, exist_ok=True)
```

2. Update `from_config` to pass the value:

```python
@staticmethod
def from_config(config: Config) -> "HistoryStore":
    return HistoryStore(
        config.history_path,
        max_history_file_size=config.max_history_file_size
    )
```

3. Update `save_message` signature and use stored value:

```python
def save_message(self, session_id: str, message: HistoryMessage) -> None:
    """Save a message to history."""
    # Get session to update
    sessions = self._read_index()
    idx = self._find_session_index(sessions, session_id)
    if idx < 0:
        raise ValueError(f"Session not found: {session_id}")

    session = sessions[idx]

    # Get current chunk and check if full
    current_idx = self._get_current_chunk_index(session_id)
    current_chunk = self._chunk_path(session_id, current_idx)
    current_count = self._count_messages_in_chunk(current_chunk)

    # If current chunk is full, create new one
    if current_count >= self.max_history_file_size:
        current_idx += 1
        current_chunk = self._chunk_path(session_id, current_idx)
        session.chunk_count = current_idx

    # ... rest unchanged
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/history.py tests/core/test_history.py
git commit -m "feat(history): use max_history_file_size config for chunk size"
```

---

## Task 5: Update agent.py save_message call

**Files:**
- Modify: `src/picklebot/core/agent.py:189-191`

**Step 1: Run existing tests to see current state**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: FAIL - `save_message() got an unexpected keyword argument 'max_history'`

**Step 2: Write minimal implementation**

Update `_persist_message` method in `src/picklebot/core/agent.py`:

```python
def _persist_message(self, message: Message) -> None:
    """Save to HistoryStore."""
    history_msg = HistoryMessage.from_message(message)
    self.context.history_store.save_message(self.session_id, history_msg)
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/core/agent.py
git commit -m "refactor(agent): remove max_history from save_message call"
```

---

## Task 6: Final verification

**Step 1: Run all tests**

Run: `uv run pytest`
Expected: All tests pass

**Step 2: Run linting**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Verify the change end-to-end**

Run: `uv run picklebot chat` and send a few messages, then verify history is stored correctly.

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add `max_history_file_size` field to Config |
| 2 | Add to API schemas |
| 3 | Add to API router |
| 4 | Update HistoryStore to use config value |
| 5 | Update agent.py to remove param |
| 6 | Final verification |
