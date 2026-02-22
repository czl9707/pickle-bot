# Session Chunking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split session history into chunked files to bound disk and memory usage.

**Architecture:** HistoryStore manages chunk files internally. Each session has `max_history` stored in HistorySession, determining chunk size. Session ID stays stable; only internal file naming changes.

**Tech Stack:** Python, Pydantic, JSONL files, pathlib

---

## Task 1: Add max_history and chunk_count to HistorySession

**Files:**
- Modify: `src/picklebot/core/history.py:18-26`
- Test: `tests/core/test_history.py`

**Step 1: Write the failing test**

Add to `tests/core/test_history.py`:

```python
class TestHistorySessionFields:
    def test_history_session_has_max_history(self):
        """HistorySession should have max_history field."""
        from picklebot.core.history import HistorySession

        session = HistorySession(
            id="test",
            agent_id="agent",
            max_history=100,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert session.max_history == 100

    def test_history_session_has_chunk_count(self):
        """HistorySession should have chunk_count field."""
        from picklebot.core.history import HistorySession

        session = HistorySession(
            id="test",
            agent_id="agent",
            max_history=100,
            chunk_count=3,
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert session.chunk_count == 3
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestHistorySessionFields -v`
Expected: FAIL with validation error (missing fields)

**Step 3: Write minimal implementation**

Modify `src/picklebot/core/history.py`:

```python
class HistorySession(BaseModel):
    """Session metadata - stored in index.jsonl."""

    id: str
    agent_id: str
    max_history: int = 50  # Maximum messages per chunk
    chunk_count: int = 1   # Number of chunk files
    title: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestHistorySessionFields -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/history.py tests/core/test_history.py
git commit -m "feat(history): add max_history and chunk_count to HistorySession"
```

---

## Task 2: Add chunk helper methods to HistoryStore

**Files:**
- Modify: `src/picklebot/core/history.py:102-127`
- Test: `tests/core/test_history.py`

**Step 1: Write the failing test**

Add to `tests/core/test_history.py`:

```python
class TestHistoryStoreChunkHelpers:
    def test_chunk_path_format(self, history_store):
        """_chunk_path should return correct path format."""
        path = history_store._chunk_path("abc-123", 1)
        assert path == history_store.sessions_path / "session-abc-123.1.jsonl"

        path = history_store._chunk_path("abc-123", 5)
        assert path == history_store.sessions_path / "session-abc-123.5.jsonl"

    def test_list_chunks_returns_empty_for_no_chunks(self, history_store):
        """_list_chunks should return empty list when no chunks exist."""
        chunks = history_store._list_chunks("no-such-session")
        assert chunks == []

    def test_list_chunks_returns_sorted_chunks(self, history_store):
        """_list_chunks should return chunks sorted by index (newest first)."""
        # Create chunk files manually
        history_store.sessions_path.mkdir(parents=True, exist_ok=True)
        (history_store.sessions_path / "session-test.1.jsonl").touch()
        (history_store.sessions_path / "session-test.3.jsonl").touch()
        (history_store.sessions_path / "session-test.2.jsonl").touch()

        chunks = history_store._list_chunks("test")
        assert len(chunks) == 3
        # Newest first (highest index)
        assert chunks[0].name == "session-test.3.jsonl"
        assert chunks[1].name == "session-test.2.jsonl"
        assert chunks[2].name == "session-test.1.jsonl"

    def test_get_current_chunk_index_returns_1_when_empty(self, history_store):
        """_get_current_chunk_index should return 1 when no chunks exist."""
        idx = history_store._get_current_chunk_index("no-session")
        assert idx == 1

    def test_get_current_chunk_index_returns_highest(self, history_store):
        """_get_current_chunk_index should return highest existing index."""
        history_store.sessions_path.mkdir(parents=True, exist_ok=True)
        (history_store.sessions_path / "session-test.1.jsonl").touch()
        (history_store.sessions_path / "session-test.5.jsonl").touch()
        (history_store.sessions_path / "session-test.3.jsonl").touch()

        idx = history_store._get_current_chunk_index("test")
        assert idx == 5

    def test_count_messages_in_chunk(self, history_store):
        """_count_messages_in_chunk should count lines in chunk file."""
        chunk_path = history_store.sessions_path / "session-test.1.jsonl"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)

        with open(chunk_path, "w") as f:
            f.write('{"role":"user","content":"msg1"}\n')
            f.write('{"role":"user","content":"msg2"}\n')
            f.write('{"role":"user","content":"msg3"}\n')

        count = history_store._count_messages_in_chunk(chunk_path)
        assert count == 3
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestHistoryStoreChunkHelpers -v`
Expected: FAIL with AttributeError

**Step 3: Write minimal implementation**

Add to `HistoryStore` class in `src/picklebot/core/history.py`:

```python
def _chunk_path(self, session_id: str, index: int) -> Path:
    """Get the file path for a session chunk."""
    return self.sessions_path / f"session-{session_id}.{index}.jsonl"

def _list_chunks(self, session_id: str) -> list[Path]:
    """List all chunk files for a session, sorted newest first."""
    pattern = f"session-{session_id}.*.jsonl"
    chunks = list(self.sessions_path.glob(pattern))
    # Sort by index (descending - newest first)
    chunks.sort(key=lambda p: int(p.name.split(".")[-2]), reverse=True)
    return chunks

def _get_current_chunk_index(self, session_id: str) -> int:
    """Get the current (highest) chunk index, or 1 if no chunks exist."""
    chunks = self._list_chunks(session_id)
    if not chunks:
        return 1
    # Extract index from filename: session-id.N.jsonl
    return int(chunks[0].name.split(".")[-2])

def _count_messages_in_chunk(self, chunk_path: Path) -> int:
    """Count the number of messages in a chunk file."""
    if not chunk_path.exists():
        return 0
    with open(chunk_path) as f:
        return sum(1 for line in f if line.strip())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestHistoryStoreChunkHelpers -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/history.py tests/core/test_history.py
git commit -m "feat(history): add chunk helper methods to HistoryStore"
```

---

## Task 3: Update create_session to use chunked file naming

**Files:**
- Modify: `src/picklebot/core/history.py:160-179`
- Test: `tests/core/test_history.py`

**Step 1: Write the failing test**

Modify `TestCreateSession.test_creates_empty_session_file`:

```python
def test_creates_empty_session_file(self, history_store):
    """create_session should create chunk file with .1.jsonl extension."""
    history_store.create_session("test-agent", "session-123", max_history=100)

    # Should create session-session-123.1.jsonl (chunk format)
    session_file = history_store.sessions_path / "session-session-123.1.jsonl"
    assert session_file.exists()
    with open(session_file) as f:
        content = f.read()
    assert content == ""

def test_create_session_stores_max_history(self, history_store):
    """create_session should store max_history in session metadata."""
    history_store.create_session("test-agent", "session-123", max_history=200)

    sessions = history_store.list_sessions()
    assert sessions[0].max_history == 200

def test_create_session_default_max_history(self, history_store):
    """create_session should use default max_history if not specified."""
    history_store.create_session("test-agent", "session-123")

    sessions = history_store.list_sessions()
    assert sessions[0].max_history == 50  # Default value
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestCreateSession -v`
Expected: FAIL (wrong filename or missing max_history)

**Step 3: Write minimal implementation**

Modify `create_session` in `src/picklebot/core/history.py`:

```python
def create_session(
    self, agent_id: str, session_id: str, max_history: int = 50
) -> dict[str, Any]:
    """Create a new conversation session."""
    now = _now_iso()
    session = HistorySession(
        id=session_id,
        agent_id=agent_id,
        max_history=max_history,
        chunk_count=1,
        title=None,
        message_count=0,
        created_at=now,
        updated_at=now,
    )

    # Append to index
    with open(self.index_path, "a") as f:
        f.write(session.model_dump_json() + "\n")

    # Create first chunk file
    self._chunk_path(session_id, 1).touch()

    return session.model_dump()
```

Also remove the old `_session_file_path` method (no longer needed):

```python
# Remove this method:
# def _session_file_path(self, session_id: str) -> Path:
#     """Get the file path for a session."""
#     return self.sessions_path / f"session-{session_id}.jsonl"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestCreateSession -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/history.py tests/core/test_history.py
git commit -m "feat(history): create_session uses chunked file naming"
```

---

## Task 4: Update save_message to handle chunking

**Files:**
- Modify: `src/picklebot/core/history.py:181-207`
- Test: `tests/core/test_history.py`

**Step 1: Write the failing test**

Add to `tests/core/test_history.py`:

```python
class TestSaveMessageChunking:
    def test_creates_new_chunk_when_full(self, history_store):
        """save_message should create new chunk when current is full."""
        history_store.create_session("agent", "session-1", max_history=3)

        # Fill first chunk (3 messages = max_history)
        for i in range(3):
            history_store.save_message(
                "session-1", HistoryMessage(role="user", content=f"msg{i}")
            )

        # Next message should create chunk 2
        history_store.save_message(
            "session-1", HistoryMessage(role="user", content="msg3")
        )

        # Both chunks should exist
        assert (history_store.sessions_path / "session-session-1.1.jsonl").exists()
        assert (history_store.sessions_path / "session-session-1.2.jsonl").exists()

        # Verify content distribution
        chunk1_count = history_store._count_messages_in_chunk(
            history_store.sessions_path / "session-session-1.1.jsonl"
        )
        chunk2_count = history_store._count_messages_in_chunk(
            history_store.sessions_path / "session-session-1.2.jsonl"
        )
        assert chunk1_count == 3
        assert chunk2_count == 1

    def test_updates_chunk_count_in_index(self, history_store):
        """save_message should update chunk_count when creating new chunk."""
        history_store.create_session("agent", "session-1", max_history=2)

        # Fill chunk 1
        history_store.save_message("session-1", HistoryMessage(role="user", content="a"))
        history_store.save_message("session-1", HistoryMessage(role="user", content="b"))

        # Create chunk 2
        history_store.save_message("session-1", HistoryMessage(role="user", content="c"))

        sessions = history_store.list_sessions()
        assert sessions[0].chunk_count == 2

    def test_appends_to_current_chunk_when_not_full(self, history_store):
        """save_message should append to current chunk when not full."""
        history_store.create_session("agent", "session-1", max_history=100)

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

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestSaveMessageChunking -v`
Expected: FAIL (no chunking logic yet)

**Step 3: Write minimal implementation**

Modify `save_message` in `src/picklebot/core/history.py`:

```python
def save_message(self, session_id: str, message: HistoryMessage) -> None:
    """Save a message to history."""
    # Get session to access max_history
    sessions = self._read_index()
    idx = self._find_session_index(sessions, session_id)
    if idx < 0:
        raise ValueError(f"Session not found: {session_id}")

    session = sessions[idx]
    max_history = session.max_history

    # Get current chunk and check if full
    current_idx = self._get_current_chunk_index(session_id)
    current_chunk = self._chunk_path(session_id, current_idx)
    current_count = self._count_messages_in_chunk(current_chunk)

    # If current chunk is full, create new one
    if current_count >= max_history:
        current_idx += 1
        current_chunk = self._chunk_path(session_id, current_idx)
        session.chunk_count = current_idx

    # Append message to chunk
    with open(current_chunk, "a") as f:
        f.write(message.model_dump_json() + "\n")

    # Update index
    session.message_count += 1
    session.updated_at = _now_iso()

    # Auto-generate title from first user message
    if session.title is None and message.role == "user":
        title = message.content[:50]
        if len(message.content) > 50:
            title += "..."
        session.title = title

    # Sort by updated_at (most recent first)
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    self._write_index(sessions)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestSaveMessageChunking -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/history.py tests/core/test_history.py
git commit -m "feat(history): save_message creates new chunks when full"
```

---

## Task 5: Update get_messages to load from multiple chunks

**Files:**
- Modify: `src/picklebot/core/history.py:226-241`
- Test: `tests/core/test_history.py`

**Step 1: Write the failing test**

Add to `tests/core/test_history.py`:

```python
class TestGetMessagesChunking:
    def test_loads_from_multiple_chunks(self, history_store):
        """get_messages should load from multiple chunks, newest first."""
        history_store.create_session("agent", "session-1", max_history=2)

        # Create 5 messages across 3 chunks
        for i in range(5):
            history_store.save_message(
                "session-1", HistoryMessage(role="user", content=f"msg{i}")
            )

        # max_history=2, so should only get last 2 messages
        messages = history_store.get_messages("session-1")
        assert len(messages) == 2
        assert messages[0].content == "msg3"
        assert messages[1].content == "msg4"

    def test_loads_all_when_less_than_max(self, history_store):
        """get_messages should return all when less than max_history."""
        history_store.create_session("agent", "session-1", max_history=100)

        history_store.save_message("session-1", HistoryMessage(role="user", content="a"))
        history_store.save_message("session-1", HistoryMessage(role="user", content="b"))

        messages = history_store.get_messages("session-1")
        assert len(messages) == 2
        assert messages[0].content == "a"
        assert messages[1].content == "b"

    def test_spans_chunks_for_max_history(self, history_store):
        """get_messages should span chunks to reach max_history."""
        history_store.create_session("agent", "session-1", max_history=3)

        # 5 messages across 2 chunks (3 in chunk 1, 2 in chunk 2)
        for i in range(5):
            history_store.save_message(
                "session-1", HistoryMessage(role="user", content=f"msg{i}")
            )

        # max_history=3, should get last 3 (1 from chunk 1, 2 from chunk 2)
        messages = history_store.get_messages("session-1")
        assert len(messages) == 3
        assert messages[0].content == "msg2"
        assert messages[1].content == "msg3"
        assert messages[2].content == "msg4"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_history.py::TestGetMessagesChunking -v`
Expected: FAIL (still reading from single file)

**Step 3: Write minimal implementation**

Modify `get_messages` in `src/picklebot/core/history.py`:

```python
def get_messages(self, session_id: str) -> list[HistoryMessage]:
    """Get messages for a session, up to max_history."""
    # Get session to access max_history
    sessions = self._read_index()
    idx = self._find_session_index(sessions, session_id)
    if idx < 0:
        return []

    max_history = sessions[idx].max_history

    # Load from chunks, newest first
    chunks = self._list_chunks(session_id)
    messages: list[HistoryMessage] = []

    for chunk in chunks:
        if not chunk.exists():
            continue

        chunk_messages: list[HistoryMessage] = []
        with open(chunk) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        chunk_messages.append(
                            HistoryMessage.model_validate_json(line)
                        )
                    except Exception:
                        continue

        # Prepend older messages
        messages = chunk_messages + messages

        # Stop if we have enough
        if len(messages) >= max_history:
            break

    # Return newest max_history messages
    return messages[-max_history:]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_history.py::TestGetMessagesChunking -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/history.py tests/core/test_history.py
git commit -m "feat(history): get_messages loads from multiple chunks"
```

---

## Task 6: Update Agent to pass max_history when creating sessions

**Files:**
- Modify: `src/picklebot/core/agent.py:81-113`
- Test: `tests/core/test_agent.py` (if exists)

**Step 1: Check existing agent tests**

Run: `uv run pytest tests/ -k agent -v`
Review output to understand test coverage.

**Step 2: Write the failing test** (if needed)

Add test to verify max_history is passed correctly based on mode.

**Step 3: Write minimal implementation**

Modify `new_session` in `src/picklebot/core/agent.py`:

```python
def new_session(self, mode: SessionMode) -> "AgentSession":
    # ... existing code ...

    # Determine max_history based on mode
    if mode == SessionMode.CHAT:
        max_history = self.context.config.chat_max_history
    else:
        max_history = self.context.config.job_max_history

    # Build tools for this session
    tools = self._build_tools(mode)

    session = AgentSession(
        session_id=session_id,
        agent_id=self.agent_def.id,
        context=self.context,
        agent=self,
        tools=tools,
        mode=mode,
        max_history=max_history,
    )

    # Pass max_history to create_session
    self.context.history_store.create_session(
        self.agent_def.id, session_id, max_history=max_history
    )
    return session
```

**Step 4: Run all tests to verify**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py
git commit -m "feat(agent): pass max_history to create_session"
```

---

## Task 7: Run full test suite and fix any regressions

**Files:**
- Various test files

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`

**Step 2: Fix any failures**

Address any test failures that arise from the changes. Update test expectations where needed (e.g., session file naming).

**Step 3: Format and lint**

Run: `uv run black . && uv run ruff check .`

**Step 4: Final verification**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "fix: update tests for session chunking"
```

---

## Summary

After all tasks complete:

1. Sessions are stored in chunked files: `session-{id}.{index}.jsonl`
2. Each chunk holds up to `max_history` messages
3. `get_messages` loads only from newest chunks, bounded by `max_history`
4. Memory and disk usage are bounded per session
