# JSONL History Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify HistoryStore with append-only JSONL format and sync file operations.

**Architecture:** Single-file history.py rewrite using JSONL (one JSON object per line). Session metadata lives in index.jsonl, messages in session-{id}.jsonl. Sync operations replace async aiofiles.

**Tech Stack:** Python stdlib (json, pathlib), Pydantic for validation

---

## Task 1: Write Tests for New JSONL HistoryStore

**Files:**
- Create: `tests/core/__init__.py`
- Create: `tests/core/test_history.py`

**Step 1: Create test directory and file**

```python
# tests/core/__init__.py
# Empty file
```

**Step 2: Write the failing tests**

```python
# tests/core/test_history.py
"""Tests for JSONL-based HistoryStore."""

import json
import tempfile
from pathlib import Path

import pytest

from picklebot.core.history import HistoryStore, HistorySession, HistoryMessage


@pytest.fixture
def temp_history_dir():
    """Create a temporary directory for history storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(temp_history_dir):
    """Create a HistoryStore instance."""
    return HistoryStore(temp_history_dir)


class TestHistoryStoreInit:
    def test_creates_directories(self, temp_history_dir):
        """HistoryStore should create required directories."""
        HistoryStore(temp_history_dir)
        assert temp_history_dir.exists()
        assert (temp_history_dir / "sessions").exists()

    def test_index_file_created_on_first_write(self, store):
        """Index file should not exist until first session created."""
        assert not store.index_path.exists()


class TestCreateSession:
    def test_creates_session(self, store):
        """create_session should return session metadata."""
        session = store.create_session("test-agent", "session-123")

        assert session["id"] == "session-123"
        assert session["agent_id"] == "test-agent"
        assert session["title"] is None
        assert session["message_count"] == 0

    def test_creates_index_entry(self, store):
        """create_session should append to index.jsonl."""
        store.create_session("test-agent", "session-123")

        with open(store.index_path) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["id"] == "session-123"

    def test_creates_empty_session_file(self, store):
        """create_session should create empty session file."""
        store.create_session("test-agent", "session-123")

        session_file = store.sessions_path / "session-session-123.jsonl"
        assert session_file.exists()
        with open(session_file) as f:
            content = f.read()
        assert content == ""

    def test_multiple_sessions(self, store):
        """Multiple sessions should be appended to index."""
        store.create_session("agent-1", "session-1")
        store.create_session("agent-2", "session-2")

        sessions = store.list_sessions()
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0].id == "session-2"
        assert sessions[1].id == "session-1"


class TestSaveMessage:
    def test_appends_message_to_session_file(self, store):
        """save_message should append line to session file."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(role="user", content="Hello")
        store.save_message("session-1", msg)

        session_file = store.sessions_path / "session-session-1.jsonl"
        with open(session_file) as f:
            lines = f.readlines()

        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["role"] == "user"
        assert entry["content"] == "Hello"

    def test_updates_message_count_in_index(self, store):
        """save_message should update message_count in index."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(role="user", content="Hello")
        store.save_message("session-1", msg)

        sessions = store.list_sessions()
        assert sessions[0].message_count == 1

    def test_auto_generates_title_from_first_user_message(self, store):
        """First user message should auto-generate session title."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(role="user", content="This is a long question that should be truncated")
        store.save_message("session-1", msg)

        sessions = store.list_sessions()
        assert sessions[0].title == "This is a long question that should be t..."

    def test_handles_tool_calls(self, store):
        """save_message should store tool_calls."""
        store.create_session("agent", "session-1")

        msg = HistoryMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "call-1", "function": {"name": "test"}}]
        )
        store.save_message("session-1", msg)

        messages = store.get_messages("session-1")
        assert messages[0].tool_calls is not None
        assert messages[0].tool_calls[0]["id"] == "call-1"


class TestGetMessages:
    def test_returns_empty_list_for_new_session(self, store):
        """get_messages should return empty list for new session."""
        store.create_session("agent", "session-1")

        messages = store.get_messages("session-1")
        assert messages == []

    def test_returns_all_messages(self, store):
        """get_messages should return all messages in order."""
        store.create_session("agent", "session-1")

        store.save_message("session-1", HistoryMessage(role="user", content="Hello"))
        store.save_message("session-1", HistoryMessage(role="assistant", content="Hi there"))

        messages = store.get_messages("session-1")
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"


class TestUpdateSessionTitle:
    def test_updates_title_in_index(self, store):
        """update_session_title should update title in index."""
        store.create_session("agent", "session-1")

        store.update_session_title("session-1", "New Title")

        sessions = store.list_sessions()
        assert sessions[0].title == "New Title"


class TestListSessions:
    def test_returns_empty_list_when_no_sessions(self, store):
        """list_sessions should return empty list initially."""
        sessions = store.list_sessions()
        assert sessions == []

    def test_returns_sessions_ordered_by_updated_at(self, store):
        """list_sessions should return most recently updated first."""
        store.create_session("agent", "session-1")
        store.create_session("agent", "session-2")

        # Update session-1
        store.save_message("session-1", HistoryMessage(role="user", content="Hi"))

        sessions = store.list_sessions()
        assert sessions[0].id == "session-1"  # Most recently updated
        assert sessions[1].id == "session-2"
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_history.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.core.history'" or similar

**Step 4: Commit**

```bash
git add tests/core/__init__.py tests/core/test_history.py
git commit -m "test: add tests for JSONL HistoryStore"
```

---

## Task 2: Rewrite HistoryStore with JSONL

**Files:**
- Modify: `src/picklebot/core/history.py`

**Step 1: Write the new implementation**

```python
"""JSONL file-based conversation history backend."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from picklebot.utils.config import Config


def _now_iso() -> str:
    """Return current datetime as ISO format string."""
    return datetime.now().isoformat()


class HistorySession(BaseModel):
    """Session metadata - stored in index.jsonl."""

    id: str
    agent_id: str
    title: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str


class HistoryMessage(BaseModel):
    """Single message - stored in session.jsonl."""

    timestamp: str = Field(default_factory=_now_iso)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class HistoryStore:
    """
    JSONL file-based history storage.

    Directory structure:
    ~/.pickle-bot/history/
    ├── index.jsonl              # Session metadata (append-only)
    └── sessions/
        └── session-{id}.jsonl   # Messages (append-only)
    """

    @staticmethod
    def from_config(config: Config) -> "HistoryStore":
        return HistoryStore(config.workspace / config.history.path)

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / "sessions"
        self.index_path = self.base_path / "index.jsonl"

        self.base_path.mkdir(parents=True, exist_ok=True)
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    def _session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_path / f"session-{session_id}.jsonl"

    def _read_index(self) -> list[HistorySession]:
        """Read all session entries from index.jsonl."""
        if not self.index_path.exists():
            return []

        sessions = []
        with open(self.index_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        sessions.append(HistorySession.model_validate_json(line))
                    except Exception:
                        continue
        return sessions

    def _write_index(self, sessions: list[HistorySession]) -> None:
        """Write all session entries to index.jsonl."""
        with open(self.index_path, "w") as f:
            for session in sessions:
                f.write(session.model_dump_json() + "\n")

    def _find_session_index(self, sessions: list[HistorySession], session_id: str) -> int:
        """Find the index of a session in the list."""
        for i, s in enumerate(sessions):
            if s.id == session_id:
                return i
        return -1

    def create_session(self, agent_id: str, session_id: str) -> dict[str, Any]:
        """Create a new conversation session."""
        now = _now_iso()
        session = HistorySession(
            id=session_id,
            agent_id=agent_id,
            title=None,
            message_count=0,
            created_at=now,
            updated_at=now,
        )

        # Append to index
        with open(self.index_path, "a") as f:
            f.write(session.model_dump_json() + "\n")

        # Create empty session file
        self._session_file_path(session_id).touch()

        return session.model_dump()

    def save_message(self, session_id: str, message: HistoryMessage) -> None:
        """Save a message to history."""
        session_file = self._session_file_path(session_id)
        if not session_file.exists():
            raise ValueError(f"Session not found: {session_id}")

        # Append message to session file
        with open(session_file, "a") as f:
            f.write(message.model_dump_json() + "\n")

        # Update index
        sessions = self._read_index()
        idx = self._find_session_index(sessions, session_id)
        if idx >= 0:
            sessions[idx].message_count += 1
            sessions[idx].updated_at = _now_iso()

            # Auto-generate title from first user message
            if sessions[idx].title is None and message.role == "user":
                title = message.content[:50]
                if len(message.content) > 50:
                    title += "..."
                sessions[idx].title = title

            # Sort by updated_at (most recent first)
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            self._write_index(sessions)

    def update_session_title(self, session_id: str, title: str) -> None:
        """Update a session's title."""
        sessions = self._read_index()
        idx = self._find_session_index(sessions, session_id)
        if idx >= 0:
            sessions[idx].title = title
            sessions[idx].updated_at = _now_iso()
            self._write_index(sessions)
        else:
            raise ValueError(f"Session not found: {session_id}")

    def list_sessions(self) -> list[HistorySession]:
        """List all sessions, most recently updated first."""
        sessions = self._read_index()
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_messages(self, session_id: str) -> list[HistoryMessage]:
        """Get all messages for a session."""
        session_file = self._session_file_path(session_id)
        if not session_file.exists():
            return []

        messages = []
        with open(session_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(HistoryMessage.model_validate_json(line))
                    except Exception:
                        continue
        return messages
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_history.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add src/picklebot/core/history.py
git commit -m "refactor: rewrite HistoryStore with JSONL format"
```

---

## Task 3: Update Session to Use Sync HistoryStore

**Files:**
- Modify: `src/picklebot/core/session.py`

**Step 1: Remove await from history calls**

Change `session.py` from async to sync history operations:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from uuid import uuid4

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionToolMessageParam,
    ChatCompletionAssistantMessageParam
)
from picklebot.utils.config import AgentConfig
from .history import HistoryStore, HistoryMessage


@dataclass
class AgentSession:
    """
    Runtime state for the pickle-bot agent.
    """

    agent_config: AgentConfig
    history_store: "HistoryStore"
    session_id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    async def __aenter__(self):
        # ensure history_store initialize the session.
        self.history_store.create_session(self.agent_config.name, self.session_id)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def add_message(self, message: Message) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)
        self._save_message_to_history(message)

    def get_history(self, max_messages: int = 50) -> list[Message]:
        """
        Get conversation history.

        Args:
            max_messages: Maximum number of messages to return

        Returns:
            List of messages in litellm format
        """
        return self.messages[-max_messages:]

    def _save_message_to_history(self, message: Message) -> None:
        """
        Persist a message to the history backend.

        Args:
            message: The message to persist (in litellm format)
        """

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
            tool_calls = tool_calls,
            tool_call_id=tool_call_id,
        )
        self.history_store.save_message(self.session_id, history_msg)
```

**Step 2: Run tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add src/picklebot/core/session.py
git commit -m "refactor: use sync HistoryStore in AgentSession"
```

---

## Task 4: Remove aiofiles Dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Remove aiofiles from dependencies**

Change pyproject.toml:

```toml
[project]
name = "pickle-bot"
version = "0.1.0"
description = "Personal AI assistant with pluggable skills"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
  "litellm>=1.0.0",
  "typer>=0.12.0",
  "textual>=0.21.0",
  "pydantic>=2.0.0",
  "pyyaml>=6.0",
  "rich>=13.0.0",
]

[project.scripts]
picklebot = "picklebot.cli.main:app"

[tool.uv.sources]

[dependency-groups]
dev = [
  "types-pyyaml",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/picklebot"]
```

**Step 2: Sync dependencies**

Run: `uv sync`
Expected: Success, aiofiles removed

**Step 3: Run tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: remove aiofiles dependency"
```

---

## Task 5: Update HistoryStore Exports

**Files:**
- Modify: `src/picklebot/core/__init__.py`

**Step 1: Update exports**

```python
from .agent import Agent
from .session import AgentSession
from .history import HistoryStore, HistorySession, HistoryMessage

__all__ = ["Agent", "AgentSession", "HistoryStore", "HistorySession", "HistoryMessage"]
```

**Step 2: Verify imports work**

Run: `uv run python -c "from picklebot.core import HistoryStore, HistoryMessage; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add src/picklebot/core/__init__.py
git commit -m "chore: update core exports for new HistoryStore"
```

---

## Task 6: Final Verification

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linting**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Manual test**

Run: `uv run picklebot chat`
Expected: Chat starts, history files created in JSONL format

**Step 4: Verify JSONL format**

Run: `cat ~/.pickle-bot/history/index.jsonl`
Expected: One JSON object per line

---

## Verification Summary

1. All tests pass: `uv run pytest -v`
2. Linting passes: `uv run ruff check . && uv run mypy .`
3. Manual test: `uv run picklebot chat` creates JSONL history files
4. File format verified: `~/.pickle-bot/history/index.jsonl` and `sessions/*.jsonl`
