# Session History Limits Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add executor-aware history limits using SessionMode enum to differentiate chat (50) vs job (500) contexts.

**Architecture:** Add `SessionMode` enum and config fields for `chat_max_history`/`job_max_history`. `Agent.new_session()` requires explicit mode, and `AgentSession` stores `max_history` at creation time.

**Tech Stack:** Python, Pydantic, pytest

---

### Task 1: Add SessionMode Enum and Config Fields

**Files:**
- Modify: `src/picklebot/core/agent.py` (add enum at top)
- Modify: `src/picklebot/utils/config.py` (add fields)
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Create `tests/utils/test_config.py`:

```python
"""Tests for session history config fields."""

import pytest
from picklebot.utils.config import Config


def test_config_default_history_limits(tmp_path):
    """Config should have default history limits."""
    config = Config(
        workspace=tmp_path,
        llm={"provider": "openai", "model": "gpt-4", "api_key": "test"},
        default_agent="test",
    )

    assert config.chat_max_history == 50
    assert config.job_max_history == 500


def test_config_custom_history_limits(tmp_path):
    """Config should allow custom history limits."""
    config = Config(
        workspace=tmp_path,
        llm={"provider": "openai", "model": "gpt-4", "api_key": "test"},
        default_agent="test",
        chat_max_history=100,
        job_max_history=1000,
    )

    assert config.chat_max_history == 100
    assert config.job_max_history == 1000


def test_config_history_limits_must_be_positive(tmp_path):
    """Config should reject non-positive history limits."""
    with pytest.raises(Exception):  # ValidationError
        Config(
            workspace=tmp_path,
            llm={"provider": "openai", "model": "gpt-4", "api_key": "test"},
            default_agent="test",
            chat_max_history=0,
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: FAIL - "Config has no field 'chat_max_history'"

**Step 3: Add SessionMode enum to agent.py**

At the top of `src/picklebot/core/agent.py`, after imports, add:

```python
from enum import Enum


class SessionMode(str, Enum):
    """Session mode determines history limit behavior."""

    CHAT = "chat"
    JOB = "job"
```

**Step 4: Add config fields to config.py**

In `src/picklebot/utils/config.py`, add to the `Config` class (around line 95-102):

```python
    chat_max_history: int = Field(default=50, gt=0)
    job_max_history: int = Field(default=500, gt=0)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/agent.py src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat: add SessionMode enum and history limit config fields"
```

---

### Task 2: Update Agent.new_session() and AgentSession

**Files:**
- Modify: `src/picklebot/core/agent.py:73-88` (new_session)
- Modify: `src/picklebot/core/agent.py:124-148` (AgentSession)

**Step 1: Write the failing test**

Add to `tests/core/test_agent.py`:

```python
from picklebot.core.agent import SessionMode


def test_agent_new_session_requires_mode(test_agent):
    """Agent.new_session should require explicit mode."""
    # This will fail at runtime if mode is not provided
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.session_id is not None
    assert session.max_history == 50  # chat default


def test_agent_new_session_job_mode(test_agent, test_config):
    """Agent.new_session with JOB mode should use job_max_history."""
    session = test_agent.new_session(SessionMode.JOB)

    assert session.max_history == test_config.job_max_history


def test_agent_new_session_chat_mode(test_agent, test_config):
    """Agent.new_session with CHAT mode should use chat_max_history."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.max_history == test_config.chat_max_history
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent.py::test_agent_new_session_requires_mode -v`
Expected: FAIL - "new_session() missing required argument 'mode'"

**Step 3: Update Agent.new_session() signature**

In `src/picklebot/core/agent.py`, update `new_session()`:

```python
def new_session(self, mode: SessionMode) -> "AgentSession":
    """
    Create a new conversation session.

    Args:
        mode: Session mode (CHAT or JOB) determines history limit

    Returns:
        A new Session instance with self as the agent reference.
    """
    session_id = str(uuid.uuid4())

    # Determine max_history based on mode
    if mode == SessionMode.CHAT:
        max_history = self.context.config.chat_max_history
    else:
        max_history = self.context.config.job_max_history

    session = AgentSession(
        session_id=session_id,
        agent_id=self.agent_def.id,
        context=self.context,
        agent=self,
        max_history=max_history,
    )

    self.context.history_store.create_session(self.agent_def.id, session_id)
    return session
```

**Step 4: Update AgentSession dataclass**

Update the `AgentSession` dataclass to add `max_history` field and use it:

```python
@dataclass
class AgentSession:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    context: SharedContext
    agent: Agent  # Reference to parent agent for LLM/tools access
    max_history: int  # Max messages to include in LLM context

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """Add a message to history (in-memory + persist)."""
        self.messages.append(message)
        self._persist_message(message)

    def get_history(self, max_messages: int | None = None) -> list[Message]:
        """Get recent messages for LLM context.

        Args:
            max_messages: Override for max messages (uses self.max_history if None)
        """
        limit = max_messages if max_messages is not None else self.max_history
        return self.messages[-limit:]
```

**Step 5: Update _build_messages to use instance max_history**

In `AgentSession._build_messages()`, change:

```python
messages.extend(self.get_history(50))
```

to:

```python
messages.extend(self.get_history())
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py::test_agent_new_session -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "feat: add required mode param to new_session, store max_history on session"
```

---

### Task 3: Fix Existing Session Tests

**Files:**
- Modify: `tests/core/test_session.py`

**Step 1: Run tests to see failures**

Run: `uv run pytest tests/core/test_session.py -v`
Expected: FAIL - "new_session() missing required argument 'mode'"

**Step 2: Update test_session.py to pass mode**

Add import and update all `new_session()` calls:

```python
"""Tests for AgentSession."""

from picklebot.core.agent import SessionMode


def test_session_creation(test_agent):
    """Session should be created with required fields including agent."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.session_id is not None
    assert session.agent_id == test_agent.agent_def.id
    assert session.agent is test_agent
    assert session.messages == []


def test_session_add_message(test_agent):
    """Session should add message to in-memory list and persist to history."""
    session = test_agent.new_session(SessionMode.CHAT)

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = test_agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(test_agent):
    """Session should limit history to max_messages."""
    session = test_agent.new_session(SessionMode.CHAT)

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages


def test_session_get_history_uses_max_history(test_agent):
    """Session should use max_history when max_messages not provided."""
    session = test_agent.new_session(SessionMode.CHAT)
    # chat_max_history default is 50, so add more than that
    for i in range(60):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history()

    assert len(history) == 50
    assert history[0]["content"] == "Message 10"  # Last 50 messages
```

**Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_session.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/core/test_session.py
git commit -m "test: update session tests to use required SessionMode param"
```

---

### Task 4: Fix Remaining Agent Tests

**Files:**
- Modify: `tests/core/test_agent.py`

**Step 1: Run tests to see failures**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: FAIL on `test_agent_new_session` (old test without mode)

**Step 2: Update the old test_agent_new_session test**

The old test needs to be updated to pass mode:

```python
def test_agent_new_session(test_agent, test_agent_def):
    """Agent should create new session with self reference."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.session_id is not None
    assert session.agent_id == test_agent_def.id
    assert session.agent is test_agent
```

**Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_agent.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/core/test_agent.py
git commit -m "test: update agent tests to use required SessionMode param"
```

---

### Task 5: Update CronExecutor

**Files:**
- Modify: `src/picklebot/core/cron_executor.py:101`

**Step 1: Update import and session creation**

Add import at top:

```python
from picklebot.core.agent import Agent, SessionMode
```

Change line 101:

```python
session = agent.new_session()
```

to:

```python
session = agent.new_session(SessionMode.JOB)
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/core/test_cron_executor.py -v`
Expected: PASS (or no test failures related to this change)

**Step 3: Commit**

```bash
git add src/picklebot/core/cron_executor.py
git commit -m "feat: use JOB mode for cron executor sessions"
```

---

### Task 6: Update MessageBusExecutor

**Files:**
- Modify: `src/picklebot/core/messagebus_executor.py:32`

**Step 1: Update import and session creation**

Add to imports:

```python
from picklebot.core.agent import SessionMode
```

Change line 32:

```python
self.session = agent.new_session()
```

to:

```python
self.session = agent.new_session(SessionMode.CHAT)
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: PASS (or no test failures related to this change)

**Step 3: Commit**

```bash
git add src/picklebot/core/messagebus_executor.py
git commit -m "feat: use CHAT mode for messagebus executor sessions"
```

---

### Task 7: Update CLI Chat

**Files:**
- Modify: `src/picklebot/cli/chat.py:26`

**Step 1: Update import and session creation**

Add to imports:

```python
from picklebot.core.agent import SessionMode
```

Change line 26:

```python
session = self.agent.new_session()
```

to:

```python
session = self.agent.new_session(SessionMode.CHAT)
```

**Step 2: Run tests to verify**

Run: `uv run pytest -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/chat.py
git commit -m "feat: use CHAT mode for CLI chat sessions"
```

---

### Task 8: Update Subagent Tool

**Files:**
- Modify: `src/picklebot/tools/subagent_tool.py:84`

**Step 1: Update import and session creation**

Add to imports (line 11 area):

```python
from picklebot.core.agent import SessionMode
```

Change line 84:

```python
session = subagent.new_session()
```

to:

```python
session = subagent.new_session(SessionMode.JOB)
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: PASS (may need to update mocks)

**Step 3: Update test mocks if needed**

In `tests/tools/test_subagent_tool.py`, ensure mocks return values correctly. The mock should work since we're just calling the method differently.

**Step 4: Commit**

```bash
git add src/picklebot/tools/subagent_tool.py
git commit -m "feat: use JOB mode for subagent dispatch sessions"
```

---

### Task 9: Final Verification

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linting and type checking**

Run: `uv run ruff check . && uv run mypy .`
Expected: No errors

**Step 3: Verify the feature works**

Manual verification that:
- Config loads with new fields
- Sessions respect mode-based limits

**Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address any remaining issues"
```
