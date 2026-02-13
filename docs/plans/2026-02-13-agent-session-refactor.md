# Agent/Session Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor Agent and Session construction to support reusable agents, cleaner architecture, and future extensibility.

**Architecture:** Introduce SharedContext for global services, make Agent reusable (one level above Session), simplify Session to lightweight state holder, pass Frontend to chat() per-call.

**Tech Stack:** Python, pytest, dataclasses, pydantic, litellm

---

## Task 1: Create SharedContext

**Files:**
- Create: `src/picklebot/core/context.py`
- Test: `tests/core/test_context.py`

**Step 1: Write the failing test**

```python
# tests/core/test_context.py
from pathlib import Path
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryStore
from picklebot.utils.config import Config

def test_shared_context_holds_config_and_history_store(tmp_path):
    """SharedContext should hold config and history_store."""
    config = Config.load(tmp_path)
    history_store = HistoryStore.from_config(config)

    context = SharedContext(config=config, history_store=history_store)

    assert context.config is config
    assert context.history_store is history_store
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_context.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.core.context'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/core/context.py
from dataclasses import dataclass
from picklebot.utils.config import Config
from picklebot.core.history import HistoryStore

@dataclass
class SharedContext:
    """Global shared state for the application."""
    config: Config
    history_store: HistoryStore
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_context.py -v`
Expected: PASS

**Step 5: Export from core `__init__.py`**

```python
# src/picklebot/core/__init__.py
# Add SharedContext to exports
from picklebot.core.context import SharedContext

# Update __all__ to include SharedContext
```

**Step 6: Commit**

```bash
git add src/picklebot/core/context.py src/picklebot/core/__init__.py tests/core/test_context.py
git commit -m "feat(core): add SharedContext dataclass"
```

---

## Task 2: Add ToolRegistry.with_builtins() Factory

**Files:**
- Modify: `src/picklebot/tools/registry.py`
- Test: `tests/tools/test_registry.py`

**Step 1: Write the failing test**

```python
# tests/tools/test_registry.py (add to existing file)
from picklebot.tools.registry import ToolRegistry

def test_tool_registry_with_builtins_creates_registry_with_tools():
    """with_builtins() should create registry with builtin tools registered."""
    registry = ToolRegistry.with_builtins()

    # Should have at least one builtin tool
    assert len(registry._tools) > 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_registry.py::test_tool_registry_with_builtins_creates_registry_with_tools -v`
Expected: FAIL with "AttributeError: type object 'ToolRegistry' has no attribute 'with_builtins'"

**Step 3: Read current ToolRegistry implementation**

Run: Read `src/picklebot/tools/registry.py` to understand current structure.

**Step 4: Write minimal implementation**

```python
# src/picklebot/tools/registry.py
# Add classmethod to ToolRegistry class

@classmethod
def with_builtins(cls) -> "ToolRegistry":
    """Create a ToolRegistry with builtin tools already registered."""
    from picklebot.tools.builtin_tools import register_builtin_tools
    registry = cls()
    register_builtin_tools(registry)
    return registry
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_registry.py::test_tool_registry_with_builtins_creates_registry_with_tools -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/tools/registry.py tests/tools/test_registry.py
git commit -m "feat(tools): add ToolRegistry.with_builtins() factory method"
```

---

## Task 3: Create New Session Class

**Files:**
- Create: `src/picklebot/core/session_new.py` (temporary, will replace old)
- Test: `tests/core/test_session.py`

**Step 1: Write the failing test for Session creation**

```python
# tests/core/test_session.py
from picklebot.core.session_new import Session
from picklebot.core.history import HistoryStore
from pathlib import Path

def test_session_creation(tmp_path):
    """Session should be created with required fields."""
    history_store = HistoryStore(tmp_path / "history")
    history_store.create_session("test-agent", "test-session-id")

    session = Session(
        session_id="test-session-id",
        agent_id="test-agent",
        history_store=history_store
    )

    assert session.session_id == "test-session-id"
    assert session.agent_id == "test-agent"
    assert session.messages == []
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_session.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.core.session_new'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/core/session_new.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionToolMessageParam,
    ChatCompletionAssistantMessageParam
)
from picklebot.core.history import HistoryStore, HistoryMessage

@dataclass
class Session:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    history_store: HistoryStore

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """Add a message to history (in-memory + persist)."""
        self.messages.append(message)
        self._persist_message(message)

    def get_history(self, max_messages: int = 50) -> list[Message]:
        """Get recent messages for LLM context."""
        return self.messages[-max_messages:]

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
        self.history_store.save_message(self.session_id, history_msg)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_session.py::test_session_creation -v`
Expected: PASS

**Step 5: Write test for add_message**

```python
# tests/core/test_session.py (add to existing file)
def test_session_add_message(tmp_path):
    """Session should add message to in-memory list and persist to history."""
    history_store = HistoryStore(tmp_path / "history")
    history_store.create_session("test-agent", "test-session-id")

    session = Session(
        session_id="test-session-id",
        agent_id="test-agent",
        history_store=history_store
    )

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = history_store.get_messages("test-session-id")
    assert len(messages) == 1
    assert messages[0].content == "Hello"
```

**Step 6: Run test to verify it passes**

Run: `uv run pytest tests/core/test_session.py::test_session_add_message -v`
Expected: PASS

**Step 7: Write test for get_history**

```python
# tests/core/test_session.py (add to existing file)
def test_session_get_history_limits_messages(tmp_path):
    """Session should limit history to max_messages."""
    history_store = HistoryStore(tmp_path / "history")
    history_store.create_session("test-agent", "test-session-id")

    session = Session(
        session_id="test-session-id",
        agent_id="test-agent",
        history_store=history_store
    )

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages
```

**Step 8: Run test to verify it passes**

Run: `uv run pytest tests/core/test_session.py::test_session_get_history_limits_messages -v`
Expected: PASS

**Step 9: Commit**

```bash
git add src/picklebot/core/session_new.py tests/core/test_session.py
git commit -m "feat(core): add new Session dataclass"
```

---

## Task 4: Refactor Agent Class

**Files:**
- Modify: `src/picklebot/core/agent.py`
- Test: `tests/core/test_agent.py`

**Step 1: Read current Agent implementation**

Run: Read `src/picklebot/core/agent.py` to understand current structure.

**Step 2: Write test for new Agent constructor**

```python
# tests/core/test_agent.py (create or add to existing)
from pathlib import Path
from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryStore
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import Config, AgentConfig
from picklebot.provider import LLMProvider

def test_agent_creation_with_new_structure(tmp_path):
    """Agent should be created with agent_config, llm, tools, context."""
    config = Config.load(tmp_path)
    history_store = HistoryStore.from_config(config)
    context = SharedContext(config=config, history_store=history_store)

    agent = Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context
    )

    assert agent.agent_config is config.agent
    assert agent.context is context
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent.py::test_agent_creation_with_new_structure -v`
Expected: FAIL (constructor signature changed)

**Step 4: Refactor Agent class**

```python
# src/picklebot/core/agent.py
# Update the Agent class:

# 1. Change constructor signature
# 2. Add new_session() method
# 3. Update chat() to take session and frontend as parameters
# 4. Update _build_messages() to take session parameter
# 5. Update _handle_tool_calls() to take session parameter
# 6. Remove session from constructor fields
```

Key changes:
- `__init__`: `(self, agent_config, llm, tools, context)` - no session, no frontend
- Add `_sessions: dict[str, Session] = field(default_factory=dict)`
- Add `new_session(self) -> Session`
- `chat(self, session, message, frontend) -> str`
- `_build_messages(self, session) -> list[Message]`

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py::test_agent_creation_with_new_structure -v`
Expected: PASS

**Step 6: Write test for new_session**

```python
# tests/core/test_agent.py (add)
def test_agent_new_session(tmp_path):
    """Agent should create new session and register it."""
    config = Config.load(tmp_path)
    history_store = HistoryStore.from_config(config)
    context = SharedContext(config=config, history_store=history_store)

    agent = Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context
    )

    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == config.agent.name
    assert session in agent._sessions.values()
```

**Step 7: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent.py::test_agent_new_session -v`
Expected: PASS

**Step 8: Commit**

```bash
git add src/picklebot/core/agent.py tests/core/test_agent.py
git commit -m "refactor(core): update Agent constructor and add new_session()"
```

---

## Task 5: Update Core Exports

**Files:**
- Modify: `src/picklebot/core/__init__.py`

**Step 1: Update exports**

```python
# src/picklebot/core/__init__.py
from picklebot.core.agent import Agent
from picklebot.core.session import AgentSession  # Keep for backward compat during migration
from picklebot.core.session_new import Session
from picklebot.core.history import HistoryStore, HistoryMessage, HistorySession
from picklebot.core.context import SharedContext

__all__ = [
    "Agent",
    "AgentSession",  # Temporary, will be removed
    "Session",
    "HistoryStore",
    "HistoryMessage",
    "HistorySession",
    "SharedContext",
]
```

**Step 2: Run all tests to verify nothing broke**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add src/picklebot/core/__init__.py
git commit -m "refactor(core): update exports with Session and SharedContext"
```

---

## Task 6: Refactor ChatLoop

**Files:**
- Modify: `src/picklebot/cli/chat.py`

**Step 1: Read current ChatLoop implementation**

Run: Read `src/picklebot/cli/chat.py` to understand current structure.

**Step 2: Refactor ChatLoop constructor**

```python
# src/picklebot/cli/chat.py
from picklebot.core import Agent, Session, HistoryStore, SharedContext
from picklebot.provider import LLMProvider
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend
from picklebot.tools.registry import ToolRegistry

class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config):
        self.config = config
        self.frontend = ConsoleFrontend(config.agent)

        # Shared layer
        self.context = SharedContext(
            config=config,
            history_store=HistoryStore.from_config(config)
        )

        # Agent (reusable, created once)
        self.agent = Agent(
            agent_config=config.agent,
            llm=LLMProvider.from_config(config.llm),
            tools=ToolRegistry.with_builtins(),
            context=self.context
        )

    async def run(self) -> None:
        """Run the interactive chat loop."""
        session = self.agent.new_session()
        self.frontend.show_welcome()

        while True:
            try:
                user_input = self.frontend.get_user_input()

                if user_input.lower() in ["quit", "exit", "q"]:
                    self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                response = await self.agent.chat(session, user_input, self.frontend)
                self.frontend.show_agent_response(response)

            except KeyboardInterrupt:
                self.frontend.show_system_message("\n[yellow]Session interrupted.[/yellow]")
                break
            except Exception as e:
                self.frontend.show_system_message(f"[red]Error: {e}[/red]")
```

**Step 3: Run all tests to verify nothing broke**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 4: Manual smoke test**

Run: `uv run picklebot chat` and verify basic chat works.

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py
git commit -m "refactor(cli): update ChatLoop to use new Agent/Session structure"
```

---

## Task 7: Remove Old AgentSession

**Files:**
- Delete: `src/picklebot/core/session.py` (old AgentSession)
- Rename: `src/picklebot/core/session_new.py` -> `src/picklebot/core/session.py`
- Modify: `src/picklebot/core/__init__.py`
- Modify: Any remaining imports

**Step 1: Find all references to AgentSession**

Run: `grep -r "AgentSession" src/ tests/` to find all usages.

**Step 2: Update imports to use Session**

Update any remaining `AgentSession` references to use `Session`.

**Step 3: Delete old session.py and rename session_new.py**

```bash
rm src/picklebot/core/session.py
mv src/picklebot/core/session_new.py src/picklebot/core/session.py
```

**Step 4: Update core/__init__.py**

```python
# src/picklebot/core/__init__.py
from picklebot.core.agent import Agent
from picklebot.core.session import Session  # Now uses new Session
from picklebot.core.history import HistoryStore, HistoryMessage, HistorySession
from picklebot.core.context import SharedContext

__all__ = [
    "Agent",
    "Session",
    "HistoryStore",
    "HistoryMessage",
    "HistorySession",
    "SharedContext",
]
```

**Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 6: Final smoke test**

Run: `uv run picklebot chat` and verify everything works.

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor(core): remove old AgentSession, use new Session class"
```

---

## Task 8: Run Full Test Suite and Lint

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors

**Step 3: Run formatter**

Run: `uv run black . --check`
Expected: All files formatted

**Step 4: Run type checker**

Run: `uv run mypy .`
Expected: No errors

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: address lint and type errors"
```

---

## Summary

After completing all tasks:
- `SharedContext` holds global services
- `Agent` is reusable, creates sessions via `new_session()`
- `Session` is lightweight state (no async context manager)
- `Frontend` is passed to `chat()` per-call
- `ChatLoop` has clean construction flow
- Old `AgentSession` is removed
