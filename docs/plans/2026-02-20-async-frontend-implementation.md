# Async Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route all output through async Frontend abstraction with error isolation.

**Architecture:** All Frontend methods become async. MessageBusFrontend wraps sends in try/catch. AgentSession.chat() calls show_message() at end. Callers no longer bypass to bus.reply().

**Tech Stack:** Python async/await, contextlib.asynccontextmanager, pytest-anyio

---

## Task 1: Update Frontend Base Class

**Files:**
- Modify: `src/picklebot/frontend/base.py`

**Step 1: Add imports and update class interface**

```python
"""Abstract base class for frontend implementations."""

from abc import ABC, abstractmethod
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncIterator


class Frontend(ABC):
    """Abstract interface for frontend implementations."""

    @abstractmethod
    async def show_welcome(self) -> None:
        """Display welcome message."""

    @abstractmethod
    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        """Display a message with optional agent context."""

    @abstractmethod
    async def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""

    @abstractmethod
    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        yield

    @abstractmethod
    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Display subagent dispatch notification."""
        yield
```

**Step 2: Run mypy to check for downstream errors**

Run: `uv run mypy src/picklebot/frontend/base.py`
Expected: May show errors in other files (expected, we'll fix them)

**Step 3: Commit**

```bash
git add src/picklebot/frontend/base.py
git commit -m "feat(frontend): update base class with async interface"
```

---

## Task 2: Update SilentFrontend

**Files:**
- Modify: `src/picklebot/frontend/base.py` (SilentFrontend class)

**Step 1: Update SilentFrontend to async**

Replace the SilentFrontend class in `base.py`:

```python
class SilentFrontend(Frontend):
    """No-op frontend for unattended execution (e.g., cron jobs)."""

    async def show_welcome(self) -> None:
        pass

    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        pass

    async def show_system_message(self, content: str) -> None:
        pass

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        yield
```

**Step 2: Run mypy to verify**

Run: `uv run mypy src/picklebot/frontend/base.py`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/frontend/base.py
git commit -m "feat(frontend): update SilentFrontend to async"
```

---

## Task 3: Update ConsoleFrontend

**Files:**
- Modify: `src/picklebot/frontend/console.py`

**Step 1: Update imports**

```python
"""Console frontend implementation using Rich."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.agent_loader import AgentDef
from .base import Frontend
```

**Step 2: Update ConsoleFrontend class**

```python
class ConsoleFrontend(Frontend):
    """Console-based frontend using Rich for formatting."""

    def __init__(self, agent_def: AgentDef):
        """
        Initialize console frontend.

        Args:
            agent_def: Agent definition
        """
        self.agent_def = agent_def
        self.console = Console()

    async def show_welcome(self) -> None:
        """Display welcome message panel."""
        self.console.print(
            Panel(
                Text(f"Welcome to {self.agent_def.name}!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        """Display a message with optional agent context."""
        if agent_id:
            self.console.print(f"[bold cyan]{agent_id}:[/bold cyan] {content}")
        else:
            self.console.print(content)

    async def show_system_message(self, content: str) -> None:
        """Display system-level message (goodbye, errors, interrupts)."""
        self.console.print(content)

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        with self.console.status(f"[grey30]{content}[/grey30]"):
            yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Display subagent dispatch start."""
        self.console.print(f"[dim]{calling_agent} -> @{target_agent}: {task}[/dim]")
        yield
```

**Step 3: Run mypy to verify**

Run: `uv run mypy src/picklebot/frontend/console.py`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/frontend/console.py
git commit -m "feat(frontend): update ConsoleFrontend to async"
```

---

## Task 4: Update MessageBusFrontend

**Files:**
- Modify: `src/picklebot/frontend/messagebus.py`

**Step 1: Rewrite MessageBusFrontend with async and error handling**

```python
"""MessageBusFrontend for posting messages to messagebus platform."""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

from picklebot.frontend.base import Frontend

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)


class MessageBusFrontend(Frontend):
    """Frontend that posts messages to messagebus platform."""

    def __init__(self, bus: "MessageBus", context: Any):
        """
        Initialize MessageBusFrontend.

        Args:
            bus: MessageBus instance for posting messages
            context: Platform-specific context for routing messages
        """
        self.bus = bus
        self.context = context

    async def show_welcome(self) -> None:
        """No-op for messagebus - no welcome on incoming messages."""
        pass

    async def show_message(
        self, content: str, agent_id: str | None = None
    ) -> None:
        """Send message via bus.reply() with error isolation."""
        if agent_id:
            content = f"[{agent_id}]: {content}"
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")

    async def show_system_message(self, content: str) -> None:
        """Send system message via bus.reply() with error isolation."""
        try:
            await self.bus.reply(content, self.context)
        except Exception as e:
            logger.warning(f"Failed to send system message: {e}")

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        """No-op for messagebus - no transient display."""
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        """Send dispatch start notification."""
        msg = f"{calling_agent}: @{target_agent.lower()} {task}"
        try:
            await self.bus.reply(msg, self.context)
        except Exception as e:
            logger.warning(f"Failed to send dispatch notification: {e}")
        yield
```

**Step 2: Run mypy to verify**

Run: `uv run mypy src/picklebot/frontend/messagebus.py`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/frontend/messagebus.py
git commit -m "feat(frontend): update MessageBusFrontend to async with error isolation"
```

---

## Task 5: Update MessageBusFrontend Tests

**Files:**
- Modify: `tests/frontend/test_messagebus_frontend.py`

**Step 1: Rewrite tests for new async interface**

```python
"""Tests for MessageBusFrontend."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from picklebot.frontend.messagebus import MessageBusFrontend
from picklebot.messagebus.base import TelegramContext


class TestMessageBusFrontend:
    """Tests for MessageBusFrontend class."""

    @pytest.fixture
    def mock_bus(self):
        """Create a mock MessageBus."""
        bus = MagicMock()
        bus.reply = AsyncMock()
        return bus

    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        return TelegramContext(user_id="123", chat_id="456")

    @pytest.fixture
    def frontend(self, mock_bus, mock_context):
        """Create a MessageBusFrontend instance."""
        return MessageBusFrontend(mock_bus, mock_context)

    @pytest.mark.anyio
    async def test_show_message_sends_via_bus(self, frontend, mock_bus, mock_context):
        """show_message should call bus.reply with content."""
        await frontend.show_message("Hello world")

        mock_bus.reply.assert_called_once_with("Hello world", mock_context)

    @pytest.mark.anyio
    async def test_show_message_with_agent_id_prefixes_content(
        self, frontend, mock_bus, mock_context
    ):
        """show_message should prefix with agent_id when provided."""
        await frontend.show_message("Hello", agent_id="pickle")

        mock_bus.reply.assert_called_once_with("[pickle]: Hello", mock_context)

    @pytest.mark.anyio
    async def test_show_system_message_sends_via_bus(
        self, frontend, mock_bus, mock_context
    ):
        """show_system_message should call bus.reply with content."""
        await frontend.show_system_message("Goodbye!")

        mock_bus.reply.assert_called_once_with("Goodbye!", mock_context)

    @pytest.mark.anyio
    async def test_show_dispatch_sends_notification(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch context manager should send notification on enter."""
        async with frontend.show_dispatch("Pickle", "Cookie", "Remember this"):
            pass

        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args
        assert call_args[0][0] == "Pickle: @cookie Remember this"
        assert call_args[0][1] == mock_context

    @pytest.mark.anyio
    async def test_show_dispatch_lowercases_target(
        self, frontend, mock_bus, mock_context
    ):
        """show_dispatch should lowercase target agent name."""
        async with frontend.show_dispatch("Agent", "MySubAgent", "Do task"):
            pass

        call_args = mock_bus.reply.call_args
        message = call_args[0][0]
        assert "@mysubagent" in message.lower()

    @pytest.mark.anyio
    async def test_show_message_error_isolation(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """show_message should catch exceptions and log warnings, not raise."""
        mock_bus.reply.side_effect = Exception("Network error")

        with caplog.at_level(logging.WARNING):
            await frontend.show_message("test message")

        assert any(
            "Failed to send message" in record.message for record in caplog.records
        )
        assert any("Network error" in record.message for record in caplog.records)

    @pytest.mark.anyio
    async def test_show_dispatch_error_isolation(
        self, frontend, mock_bus, mock_context, caplog
    ):
        """show_dispatch should catch exceptions and log warnings, not raise."""
        mock_bus.reply.side_effect = Exception("API error")

        with caplog.at_level(logging.WARNING):
            async with frontend.show_dispatch("Pickle", "Cookie", "task"):
                pass

        assert any(
            "Failed to send dispatch notification" in record.message
            for record in caplog.records
        )
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/frontend/test_messagebus_frontend.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/frontend/test_messagebus_frontend.py
git commit -m "test(frontend): update MessageBusFrontend tests for async interface"
```

---

## Task 6: Update AgentSession.chat()

**Files:**
- Modify: `src/picklebot/core/agent.py`

**Step 1: Add agent_id property to AgentSession**

In the `AgentSession` dataclass, the `agent_id` field already exists. We need to ensure it's used in chat().

**Step 2: Update chat() to call show_message()**

Find the `chat` method and modify the end:

```python
async def chat(self, message: str, frontend: "Frontend") -> str:
    # ... existing logic until the final return ...

    # At the end, instead of just returning:
    await frontend.show_message(content, agent_id=self.agent_id)
    return content  # Still return for history/other purposes
```

The full change - replace the end of the method:

```python
            continue

    # Show response via frontend
    await frontend.show_message(content, agent_id=self.agent_id)
    return content
```

**Step 3: Update show_transient to async context manager**

The `show_transient` call needs to use async with:

```python
async with frontend.show_transient(display_content):
    messages = self._build_messages()
    content, tool_calls = await self.agent.llm.chat(messages, tool_schemas)
    # ... rest of the logic inside the context
```

**Step 4: Update _execute_tool_call similarly**

```python
async with frontend.show_transient(tool_display):
    try:
        result = await self.tools.execute_tool(
            tool_call.name, frontend=frontend, **args
        )
    except Exception as e:
        result = f"Error executing tool: {e}"

    return result
```

**Step 5: Run mypy to verify**

Run: `uv run mypy src/picklebot/core/agent.py`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/agent.py
git commit -m "feat(agent): call show_message() at end of chat()"
```

---

## Task 7: Update ChatLoop

**Files:**
- Modify: `src/picklebot/cli/chat.py`

**Step 1: Update user input echo to use async**

The user input echo should still work. Update the show_message calls:

```python
# Show user message
await self.frontend.show_message(
    f"[bold green]You:[/bold green] {user_input}"
)

# Get response (now also shows via frontend internally)
response = await session.chat(user_input, self.frontend)

# Remove the old manual response display - chat() handles it now
```

**Step 2: Update show_system_message calls**

```python
self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
# becomes:
await self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
```

**Step 3: Full updated run() method**

```python
async def run(self) -> None:
    """Run the interactive chat loop."""
    session = self.agent.new_session(SessionMode.CHAT)
    await self.frontend.show_welcome()

    while True:
        try:
            user_input = self.frontend.console.input(
                "[bold green]You:[/bold green] "
            )

            if user_input.lower() in ["quit", "exit", "q"]:
                await self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                break

            if not user_input.strip():
                continue

            # Show user message (raw, no agent_id)
            await self.frontend.show_message(
                f"[bold green]You:[/bold green] {user_input}"
            )

            # Get response (chat() calls show_message internally)
            await session.chat(user_input, self.frontend)

        except KeyboardInterrupt:
            await self.frontend.show_system_message(
                "\n[yellow]Session interrupted.[/yellow]"
            )
            break
        except Exception as e:
            await self.frontend.show_system_message(f"[red]Error: {e}[/red]")
```

**Step 4: Run mypy to verify**

Run: `uv run mypy src/picklebot/cli/chat.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/cli/chat.py
git commit -m "feat(cli): update ChatLoop to use async frontend"
```

---

## Task 8: Update MessageBusExecutor

**Files:**
- Modify: `src/picklebot/core/messagebus_executor.py`

**Step 1: Remove direct bus.reply() calls**

The `_process_messages` method currently calls `bus.reply()` directly. Remove that since `chat()` now handles it:

```python
async def _process_messages(self) -> None:
    """Worker that processes messages sequentially from queue."""
    while True:
        message, platform, context = await self.message_queue.get()

        logger.info(f"Processing message from {platform}")

        # Create MessageBusFrontend for this message
        bus = self.bus_map[platform]
        frontend = MessageBusFrontend(bus, context)

        try:
            # chat() handles sending response via frontend
            await self.session.chat(message, frontend)
            logger.info(f"Processed message from {platform}")
        except Exception as e:
            logger.error(f"Error processing message from {platform}: {e}")
            # Send error message via frontend
            try:
                await frontend.show_system_message(
                    "Sorry, I encountered an error processing your message."
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
        finally:
            self.message_queue.task_done()
```

**Step 2: Run mypy to verify**

Run: `uv run mypy src/picklebot/core/messagebus_executor.py`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/core/messagebus_executor.py
git commit -m "feat(messagebus): route all output through frontend"
```

---

## Task 9: Update MessageBusExecutor Tests

**Files:**
- Modify: `tests/core/test_messagebus_executor.py`

**Step 1: Update tests to verify frontend routing**

The tests should verify that responses are sent via the frontend, not direct bus.reply():

```python
@pytest.mark.anyio
async def test_processes_queue_via_frontend(self, executor_with_mock_bus):
    """Test that messages are processed and sent via frontend."""
    executor, bus = executor_with_mock_bus

    with patch.object(
        executor.session, "chat", new_callable=AsyncMock
    ) as mock_chat:
        # chat() now just runs, frontend sends the response
        mock_chat.return_value = "Test response"

        ctx = MockContext(user_id="user123", chat_id="chat456")
        await executor._enqueue_message("Hello", "mock", ctx)

        task = asyncio.create_task(executor._process_messages())
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify chat was called
        mock_chat.assert_called_once()
        # Verify bus.reply was called (via frontend)
        assert len(bus.messages_sent) >= 1
```

**Step 2: Run tests to verify**

Run: `uv run pytest tests/core/test_messagebus_executor.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/core/test_messagebus_executor.py
git commit -m "test(messagebus): update tests for frontend routing"
```

---

## Task 10: Update Subagent Dispatch Tool

**Files:**
- Modify: `src/picklebot/tools/subagent_tool.py`

**Step 1: Use async dispatch context manager**

Update the `subagent_dispatch` function:

```python
@tool(
    name="subagent_dispatch",
    description=f"Dispatch a task to a specialized subagent.\n{agents_desc}",
    parameters={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "enum": dispatchable_ids,
                "description": "ID of the agent to dispatch to",
            },
            "task": {
                "type": "string",
                "description": "The task for the subagent to perform",
            },
            "context": {
                "type": "string",
                "description": "Optional context information for the subagent",
            },
        },
        "required": ["agent_id", "task"],
    },
)
async def subagent_dispatch(
    frontend: "Frontend", agent_id: str, task: str, context: str = ""
) -> str:
    """Dispatch task to subagent, return result + session_id."""
    from picklebot.core.agent import Agent, SessionMode

    try:
        target_def = shared_context.agent_loader.load(agent_id)
    except DefNotFoundError:
        raise ValueError(f"Agent '{agent_id}' not found")

    subagent = Agent(target_def, shared_context)

    user_message = task
    if context:
        user_message = f"{task}\n\nContext:\n{context}"

    # Use dispatch context manager for notification
    async with frontend.show_dispatch(current_agent_id, agent_id, task):
        session = subagent.new_session(SessionMode.JOB)
        response = await session.chat(user_message, SilentFrontend())

    # Show result via show_message with subagent's agent_id
    await frontend.show_message(response, agent_id=agent_id)

    # Return result + session_id as JSON
    result = {
        "result": response,
        "session_id": session.session_id,
    }
    return json.dumps(result)
```

**Step 2: Run mypy to verify**

Run: `uv run mypy src/picklebot/tools/subagent_tool.py`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/tools/subagent_tool.py
git commit -m "feat(tools): use async dispatch context in subagent_tool"
```

---

## Task 11: Run Full Test Suite

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors

**Step 3: Run formatter**

Run: `uv run black .`
Expected: No changes (or formatted files)

**Step 4: Run type checker**

Run: `uv run mypy .`
Expected: No errors

---

## Task 12: Final Commit

**Files:**
- None (verification only)

**Step 1: Verify git status**

Run: `git status`
Expected: Clean (all changes committed)

**Step 2: Push to remote (optional)**

Run: `git push origin main`
Expected: Success
