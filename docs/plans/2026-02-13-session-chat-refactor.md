# Session Chat Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move `chat()` from Agent to Session for a cleaner API where sessions own conversation flow.

**Architecture:** Session holds a reference to its parent Agent and uses `self.agent.llm`, `self.agent.tools`, `self.agent.agent_config` for chat. Agent becomes a factory + config holder.

**Tech Stack:** Python dataclasses, asyncio, litellm

---

## Task 1: Add Agent Reference to Session

**Files:**
- Modify: `src/picklebot/core/session.py:1-11`
- Modify: `src/picklebot/core/agent.py:36-51`
- Test: `tests/core/test_session.py`
- Test: `tests/core/test_agent.py`

**Step 1: Update Session to accept agent parameter**

In `src/picklebot/core/session.py`, update the Session dataclass to include an `agent` field. Add `from __future__ import annotations` at the top for forward reference.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, cast
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionToolMessageParam,
    ChatCompletionAssistantMessageParam,
)
from picklebot.core.history import HistoryStore, HistoryMessage

if TYPE_CHECKING:
    from picklebot.core.agent import Agent


@dataclass
class Session:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    history_store: HistoryStore
    agent: Agent  # Reference to parent agent for LLM/tools access

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
```

**Step 2: Update Agent.new_session() to pass self**

In `src/picklebot/core/agent.py`, update `new_session()` to pass `self` to Session:

```python
def new_session(self) -> Session:
    """
    Create a new conversation session.

    Returns:
        A new Session instance registered with this agent.
    """
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        agent_id=self.agent_config.name,
        history_store=self.context.history_store,
        agent=self,  # Pass self reference
    )
    # Create session in history store
    self.context.history_store.create_session(self.agent_config.name, session_id)
    return session
```

**Step 3: Update Session tests to include agent parameter**

In `tests/core/test_session.py`, create a helper function and update tests:

```python
from pathlib import Path
from picklebot.core.session import Session
from picklebot.core.agent import Agent
from picklebot.core.history import HistoryStore
from picklebot.core.context import SharedContext
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import Config
from picklebot.provider import LLMProvider


def _create_test_agent(tmp_path: Path) -> Agent:
    """Create a minimal test agent."""
    config_file = tmp_path / "config.system.yaml"
    config_file.write_text(
        """
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
"""
    )
    config = Config.load(tmp_path)
    history_store = HistoryStore.from_config(config)
    context = SharedContext(config=config, history_store=history_store)

    return Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )


def test_session_creation(tmp_path):
    """Session should be created with required fields including agent."""
    agent = _create_test_agent(tmp_path)
    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == agent.agent_config.name
    assert session.agent is agent
    assert session.messages == []


def test_session_add_message(tmp_path):
    """Session should add message to in-memory list and persist to history."""
    agent = _create_test_agent(tmp_path)
    session = agent.new_session()

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(tmp_path):
    """Session should limit history to max_messages."""
    agent = _create_test_agent(tmp_path)
    session = agent.new_session()

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages
```

**Step 4: Update Agent tests**

In `tests/core/test_agent.py`, update tests to use new Session structure:

```python
"""Tests for the Agent class."""

from pathlib import Path
from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryStore
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import Config
from picklebot.provider import LLMProvider


def _create_test_config(tmp_path: Path) -> Config:
    """Create a minimal test config file."""
    config_file = tmp_path / "config.system.yaml"
    config_file.write_text(
        """
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
"""
    )
    return Config.load(tmp_path)


def test_agent_creation_with_new_structure(tmp_path: Path) -> None:
    """Agent should be created with agent_config, llm, tools, context."""
    config = _create_test_config(tmp_path)
    history_store = HistoryStore.from_config(config)
    context = SharedContext(config=config, history_store=history_store)

    agent = Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )

    assert agent.agent_config is config.agent
    assert agent.context is context


def test_agent_new_session(tmp_path: Path) -> None:
    """Agent should create new session with self reference."""
    config = _create_test_config(tmp_path)
    history_store = HistoryStore.from_config(config)
    context = SharedContext(config=config, history_store=history_store)

    agent = Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )

    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == config.agent.name
    assert session.agent is agent
```

**Step 5: Run tests to verify**

Run: `uv run pytest tests/core/test_session.py tests/core/test_agent.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/core/session.py src/picklebot/core/agent.py tests/core/test_session.py tests/core/test_agent.py
git commit -m "refactor(core): add agent reference to Session"
```

---

## Task 2: Move Chat Logic to Session

**Files:**
- Modify: `src/picklebot/core/session.py`
- Modify: `src/picklebot/core/agent.py`

**Step 1: Add imports to Session**

Add the necessary imports to `src/picklebot/core/session.py`:

```python
from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, cast

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionToolMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageToolCallParam,
)

from picklebot.core.history import HistoryStore, HistoryMessage

if TYPE_CHECKING:
    from picklebot.frontend import Frontend
    from picklebot.provider import LLMToolCall
```

**Step 2: Move chat method to Session**

Add the `chat()` method and helper methods to Session class:

```python
async def chat(self, message: str, frontend: "Frontend") -> str:
    """
    Send a message to the LLM and get a response.

    Args:
        message: User message
        frontend: Frontend for displaying output

    Returns:
        Assistant's response text
    """
    user_msg: Message = {"role": "user", "content": message}
    self.add_message(user_msg)

    tool_schemas = self.agent.tools.get_tool_schemas()
    tool_count = 0
    display_content = "Thinking"

    while True:
        with frontend.show_transient(display_content):
            messages = self._build_messages()
            content, tool_calls = await self.agent.llm.chat(messages, tool_schemas)

            tool_call_dicts: list[ChatCompletionMessageToolCallParam] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]
            assistant_msg: Message = {"role": "assistant", "content": content, "tool_calls": tool_call_dicts}

            self.add_message(assistant_msg)

            if not tool_calls:
                break

            await self._handle_tool_calls(tool_calls, content, frontend)
            tool_count += len(tool_calls)

            display_content = f"{content}\n - Total Tools Used: {tool_count}"

            continue

    return content

def _build_messages(self) -> list[Message]:
    """
    Build messages for LLM API call.

    Returns:
        List of messages compatible with litellm
    """
    messages: list[Message] = [
        {"role": "system", "content": self.agent.agent_config.system_prompt}
    ]
    messages.extend(self.get_history(50))

    return messages

async def _handle_tool_calls(
    self,
    tool_calls: list["LLMToolCall"],
    llm_content: str,
    frontend: "Frontend",
) -> None:
    """
    Handle tool calls from the LLM response.

    Args:
        tool_calls: List of tool calls from LLM response
        llm_content: LLM's text content alongside tool calls
        frontend: Frontend for displaying output
    """
    from picklebot.provider import LLMToolCall

    tool_call_results = await asyncio.gather(
        *[
            self._execute_tool_call(tool_call, llm_content, frontend)
            for tool_call in tool_calls
        ]
    )

    for tool_call, result in zip(tool_calls, tool_call_results):
        tool_msg: Message = {
            "role": "tool",
            "content": result,
            "tool_call_id": tool_call.id,
        }
        self.add_message(tool_msg)

async def _execute_tool_call(
    self,
    tool_call: "LLMToolCall",
    llm_content: str,
    frontend: "Frontend",
) -> str:
    """
    Execute a single tool call.

    Args:
        tool_call: Tool call from LLM response
        llm_content: LLM's text content alongside tool calls
        frontend: Frontend for displaying output

    Returns:
        Tool execution result
    """
    # Extract key arguments for display
    try:
        args = json.loads(tool_call.arguments)
    except json.JSONDecodeError:
        args = {}

    tool_display = f"Making Tool Call: {tool_call.name} {tool_call.arguments}"
    if len(tool_display) > 40:
        tool_display = tool_display[:40] + "..."

    with frontend.show_transient(tool_display):
        try:
            result = await self.agent.tools.execute_tool(tool_call.name, **args)
        except Exception as e:
            result = f"Error executing tool: {e}"

        return result
```

**Step 3: Remove chat methods from Agent**

In `src/picklebot/core/agent.py`, remove the `chat()`, `_build_messages()`, `_handle_tool_calls()`, and `_execute_tool_call()` methods. The Agent class should now be minimal:

```python
import uuid
from dataclasses import dataclass

from picklebot.core.context import SharedContext
from picklebot.core.session import Session
from picklebot.provider import LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import AgentConfig


@dataclass
class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM, tools, and config
    that sessions use for chatting.
    """

    agent_config: AgentConfig
    llm: LLMProvider
    tools: ToolRegistry
    context: SharedContext

    def new_session(self) -> Session:
        """
        Create a new conversation session.

        Returns:
            A new Session instance with self as the agent reference.
        """
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            agent_id=self.agent_config.name,
            history_store=self.context.history_store,
            agent=self,
        )
        # Create session in history store
        self.context.history_store.create_session(self.agent_config.name, session_id)
        return session
```

**Step 4: Run tests to verify**

Run: `uv run pytest tests/core/ -v`

Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/session.py src/picklebot/core/agent.py
git commit -m "refactor(core): move chat logic from Agent to Session"
```

---

## Task 3: Update ChatLoop to Use Session.chat()

**Files:**
- Modify: `src/picklebot/cli/chat.py`

**Step 1: Update the chat call**

In `src/picklebot/cli/chat.py`, change line 41 from:

```python
response = await self.agent.chat(session, user_input, self.frontend)
```

To:

```python
response = await session.chat(user_input, self.frontend)
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/ -v`

Expected: All tests pass

**Step 3: Commit**

```bash
git add src/picklebot/cli/chat.py
git commit -m "refactor(cli): use session.chat() instead of agent.chat()"
```

---

## Task 4: Run Full Test Suite and Fix Issues

**Files:**
- Any files with remaining issues

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`

Expected: All tests pass

**Step 2: Run linting and type checking**

Run: `uv run ruff check . && uv run mypy .`

Expected: No errors

**Step 3: Fix any issues**

If any errors occur, fix them.

**Step 4: Final commit**

```bash
git add -A
git commit -m "fix: address lint and type errors from session chat refactor"
```
