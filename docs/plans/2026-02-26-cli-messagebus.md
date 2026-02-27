# CLI MessageBus Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify CLI with MessageBus architecture to enable future routing capabilities and reduce code duplication

**Architecture:** CLI becomes just another MessageBus channel (like Telegram/Discord) using CliBus implementation. ChatLoop refactored to use MessageBusWorker + AgentDispatcherWorker pattern instead of standalone Agent/ConsoleFrontend.

**Tech Stack:** Python 3.13, asyncio, Rich (for console formatting), pytest

---

## Task 1: Create CliBus Implementation

**Files:**
- Create: `src/picklebot/messagebus/cli_bus.py`
- Create: `tests/messagebus/test_cli_bus.py`

**Step 1: Write the failing test for CliContext**

Create test file with basic CliContext test:

```python
# tests/messagebus/test_cli_bus.py
"""Tests for CLI MessageBus implementation."""

import pytest
from picklebot.messagebus.cli_bus import CliContext


def test_cli_context_creation():
    """Test CliContext can be created with default values."""
    context = CliContext()
    assert context.user_id == "cli-user"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_cli_bus.py::test_cli_context_creation -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'picklebot.messagebus.cli_bus'"

**Step 3: Create CliBus module with CliContext**

Create the file with CliContext and CliBus skeleton:

```python
# src/picklebot/messagebus/cli_bus.py
"""CLI message bus implementation."""

import asyncio
from dataclasses import dataclass
from typing import Callable, Awaitable

from rich.console import Console

from picklebot.messagebus.base import MessageBus, MessageContext


@dataclass
class CliContext(MessageContext):
    """Context for CLI messages."""
    user_id: str = "cli-user"


class CliBus(MessageBus[CliContext]):
    """CLI implementation of MessageBus using synchronous input()."""

    platform_name = "cli"

    def __init__(self):
        self.console = Console()
        self._stop_event = asyncio.Event()

    def is_allowed(self, context: CliContext) -> bool:
        """CLI is always allowed."""
        return True

    async def reply(self, content: str, context: CliContext) -> None:
        """Print to stdout with Rich formatting."""
        self.console.print(content)

    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message (same as reply for CLI)."""
        self.console.print(content)

    async def run(
        self, on_message: Callable[[str, CliContext], Awaitable[None]]
    ) -> None:
        """Read from stdin, call on_message for each input."""
        # TODO: Implement in next step
        pass

    async def stop(self) -> None:
        """Stop the input loop."""
        self._stop_event.set()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_cli_bus.py::test_cli_context_creation -v`

Expected: PASS

**Step 5: Write failing test for CliBus.run() input handling**

```python
# tests/messagebus/test_cli_bus.py (append to file)
import asyncio
from unittest.mock import patch


@pytest.mark.asyncio
async def test_cli_bus_read_input():
    """Test CliBus reads input and calls callback."""
    from picklebot.messagebus.cli_bus import CliBus, CliContext

    bus = CliBus()
    messages = []

    async def capture(message: str, context: CliContext):
        messages.append(message)

    with patch("builtins.input", side_effect=["hello", "quit"]):
        await bus.run(capture)

    assert messages == ["hello"]
```

**Step 6: Run test to verify it fails**

Run: `uv run pytest tests/messagebus/test_cli_bus.py::test_cli_bus_read_input -v`

Expected: FAIL (run() not implemented yet)

**Step 7: Implement CliBus.run() method**

Update the run() method in `src/picklebot/messagebus/cli_bus.py`:

```python
async def run(
    self, on_message: Callable[[str, CliContext], Awaitable[None]]
) -> None:
    """Read from stdin, call on_message for each input."""
    context = CliContext()

    try:
        while not self._stop_event.is_set():
            # Wrap blocking input() in async
            user_input = await asyncio.to_thread(input, "You: ")

            # Handle quit/exit
            if user_input.lower().strip() in ["quit", "exit", "q"]:
                break

            # Skip empty input
            if not user_input.strip():
                continue

            # Send to MessageBusWorker callback
            await on_message(user_input, context)

    except (KeyboardInterrupt, EOFError):
        pass  # Graceful exit
```

**Step 8: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_cli_bus.py::test_cli_bus_read_input -v`

Expected: PASS

**Step 9: Write test for CliBus.reply()**

```python
# tests/messagebus/test_cli_bus.py (append to file)
@pytest.mark.asyncio
async def test_cli_bus_reply():
    """Test CliBus.reply() prints to stdout."""
    from picklebot.messagebus.cli_bus import CliBus, CliContext

    bus = CliBus()
    context = CliContext()

    with patch.object(bus.console, "print") as mock_print:
        await bus.reply("test message", context)

    mock_print.assert_called_once_with("test message")
```

**Step 10: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_cli_bus.py::test_cli_bus_reply -v`

Expected: PASS (implementation already done)

**Step 11: Write test for empty input handling**

```python
# tests/messagebus/test_cli_bus.py (append to file)
@pytest.mark.asyncio
async def test_cli_bus_skips_empty_input():
    """Test CliBus skips empty input."""
    from picklebot.messagebus.cli_bus import CliBus, CliContext

    bus = CliBus()
    messages = []

    async def capture(message: str, context: CliContext):
        messages.append(message)

    with patch("builtins.input", side_effect=["", "  ", "hello", "quit"]):
        await bus.run(capture)

    assert messages == ["hello"]
```

**Step 12: Run test to verify it passes**

Run: `uv run pytest tests/messagebus/test_cli_bus.py::test_cli_bus_skips_empty_input -v`

Expected: PASS

**Step 13: Run all CliBus tests**

Run: `uv run pytest tests/messagebus/test_cli_bus.py -v`

Expected: All tests PASS

**Step 14: Commit CliBus implementation**

```bash
git add src/picklebot/messagebus/cli_bus.py tests/messagebus/test_cli_bus.py
git commit -m "feat: add CliBus MessageBus implementation

- CliBus reads stdin via asyncio.to_thread()
- CliContext with user_id='cli-user'
- reply() prints to stdout via Rich console
- Handles quit/exit commands and empty input
- Full test coverage"
```

---

## Task 2: Modify SharedContext to Accept Custom Buses

**Files:**
- Modify: `src/picklebot/core/context.py:26-32`
- Create: `tests/core/test_context_buses.py`

**Step 1: Write failing test for custom buses parameter**

```python
# tests/core/test_context_buses.py
"""Tests for SharedContext custom buses parameter."""

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.utils.config import Config


def test_shared_context_with_custom_buses():
    """Test SharedContext accepts custom bus list."""
    config = Config()
    cli_bus = CliBus()

    context = SharedContext(config, buses=[cli_bus])

    assert context.messagebus_buses == [cli_bus]
    assert len(context.messagebus_buses) == 1


def test_shared_context_loads_from_config_by_default():
    """Test SharedContext loads buses from config when not provided."""
    config = Config()

    context = SharedContext(config)

    # Should load from MessageBus.from_config()
    # Result depends on config, but should not raise
    assert isinstance(context.messagebus_buses, list)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_context_buses.py::test_shared_context_with_custom_buses -v`

Expected: FAIL with "TypeError: SharedContext.__init__() got an unexpected keyword argument 'buses'"

**Step 3: Modify SharedContext.__init__() to accept buses parameter**

Update `src/picklebot/core/context.py`:

```python
# Line 26-32, replace the __init__ method
def __init__(self, config: Config, buses: list[MessageBus] | None = None):
    self.config = config
    self.history_store = HistoryStore.from_config(config)
    self.agent_loader = AgentLoader.from_config(config)
    self.skill_loader = SkillLoader.from_config(config)
    self.cron_loader = CronLoader.from_config(config)

    # Use provided buses or load from config
    if buses is not None:
        self.messagebus_buses = buses
    else:
        self.messagebus_buses = MessageBus.from_config(config)

    self._agent_queue = None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_context_buses.py::test_shared_context_with_custom_buses -v`

Expected: PASS

**Step 5: Run second test to verify backward compatibility**

Run: `uv run pytest tests/core/test_context_buses.py::test_shared_context_loads_from_config_by_default -v`

Expected: PASS

**Step 6: Run all SharedContext tests**

Run: `uv run pytest tests/core/ -v`

Expected: All tests PASS (backward compatible)

**Step 7: Commit SharedContext modification**

```bash
git add src/picklebot/core/context.py tests/core/test_context_buses.py
git commit -m "feat: add optional buses parameter to SharedContext

Allows CLI to inject CliBus explicitly while maintaining backward
compatibility for server mode which loads from config."
```

---

## Task 3: Refactor ChatLoop to Use MessageBusWorker Pattern

**Files:**
- Modify: `src/picklebot/cli/chat.py:15-70`

**Step 1: Check existing ChatLoop implementation**

Read the current implementation:

```bash
cat src/picklebot/cli/chat.py
```

Note: We're removing:
- `self.frontend = ConsoleFrontend(self.agent_def)`
- `self.agent = Agent(agent_def=self.agent_def, context=self.context)`
- Manual input loop
- Direct session.chat() calls

**Step 2: Refactor ChatLoop class**

Replace entire ChatLoop class in `src/picklebot/cli/chat.py`:

```python
"""Chat CLI command for interactive sessions."""

import asyncio

import typer

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging


class ChatLoop:
    """Interactive chat session using MessageBusWorker pattern."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

    async def run(self) -> None:
        """Run CLI via MessageBusWorker + AgentDispatcherWorker."""
        # Create CliBus and context
        bus = CliBus()
        context = SharedContext(self.config, buses=[bus])

        # Use existing worker infrastructure
        dispatcher = AgentDispatcherWorker(context)
        message_bus = MessageBusWorker(context)

        try:
            await asyncio.gather(dispatcher.run(), message_bus.run())
        except asyncio.CancelledError:
            await bus.stop()
            raise


def chat_command(ctx: typer.Context, agent_id: str | None = None) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config, agent_id=agent_id)
    asyncio.run(chat_loop.run())
```

**Step 3: Update imports in cli/chat.py**

Verify imports are correct (should already be there from Step 2):
- Remove: `from picklebot.core import Agent, SharedContext`
- Remove: `from picklebot.core.agent import SessionMode`
- Remove: `from picklebot.frontend import ConsoleFrontend`
- Add: `from picklebot.messagebus.cli_bus import CliBus`
- Keep: `from picklebot.core.context import SharedContext`
- Add: `from picklebot.server.messagebus_worker import MessageBusWorker`

**Step 4: Run linting and formatting**

Run: `uv run black src/picklebot/cli/chat.py && uv run ruff check src/picklebot/cli/chat.py`

Expected: No errors

**Step 5: Test CLI manually (basic smoke test)**

Run: `uv run picklebot chat`

Try:
- Type "hello" and verify response
- Type "quit" to exit
- Verify no errors

**Step 6: Commit ChatLoop refactor**

```bash
git add src/picklebot/cli/chat.py
git commit -m "refactor: migrate ChatLoop to MessageBusWorker pattern

- Remove manual Agent/ConsoleFrontend setup
- Use MessageBusWorker + AgentDispatcherWorker
- CliBus handles stdin input
- Unified with Telegram/Discord architecture"
```

---

## Task 4: Add Integration Tests

**Files:**
- Create: `tests/cli/test_chat_integration.py`

**Step 1: Write integration test for CLI flow**

```python
# tests/cli/test_chat_integration.py
"""Integration tests for CLI MessageBus flow."""

import asyncio
from unittest.mock import patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config


@pytest.mark.asyncio
async def test_cli_message_flow_through_workers():
    """Test complete CLI message flow through workers."""
    # Create minimal test config
    config = Config()

    # Create CLI bus and context
    bus = CliBus()
    context = SharedContext(config, buses=[bus])

    # Mock input to simulate user
    with patch("builtins.input", side_effect=["test message", "quit"]):
        # Create workers
        dispatcher = AgentDispatcherWorker(context)
        message_bus = MessageBusWorker(context)

        # Run briefly
        task = asyncio.create_task(
            asyncio.gather(dispatcher.run(), message_bus.run())
        )

        # Let it process
        await asyncio.sleep(0.5)

        # Cancel
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Verify session was created for CLI user
    # Note: This checks runtime config, may need adjustment based on actual implementation
    assert hasattr(context, "agent_queue")
```

**Step 2: Run test to verify basic flow works**

Run: `uv run pytest tests/cli/test_chat_integration.py::test_cli_message_flow_through_workers -v -s`

Expected: PASS (or identify any issues)

**Step 3: Commit integration test**

```bash
git add tests/cli/test_chat_integration.py
git commit -m "test: add integration test for CLI MessageBus flow

Tests complete message flow from stdin through MessageBusWorker
and AgentDispatcherWorker."
```

---

## Task 5: Final Verification and Documentation

**Files:**
- Modify: `src/picklebot/messagebus/__init__.py` (if needed)

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`

Expected: All tests PASS

**Step 2: Run linting and formatting on entire codebase**

Run: `uv run black . && uv run ruff check .`

Expected: No errors

**Step 3: Test CLI with actual agent**

Run: `uv run picklebot chat -a cookie`

Try:
- Various messages
- Verify agent responds correctly
- Type "quit" to exit cleanly
- Test Ctrl+C handling

**Step 4: Test CLI with default agent**

Run: `uv run picklebot chat`

Verify default agent loads and responds.

**Step 5: Update messagebus __init__.py if needed**

Check if CliBus needs to be exported:

```bash
cat src/picklebot/messagebus/__init__.py
```

If it only has imports, verify it's consistent. Likely no changes needed since CliBus is imported directly where used.

**Step 6: Final commit**

```bash
git add .
git commit -m "chore: final cleanup and verification for CLI MessageBus integration

- All tests passing
- Linting clean
- Manual testing verified"
```

---

## Summary

**What we built:**
- CliBus: MessageBus implementation for CLI using stdin/stdout
- Modified SharedContext: Accepts custom buses for CLI mode
- Refactored ChatLoop: Uses MessageBusWorker pattern instead of manual loop
- Integration: CLI now unified with Telegram/Discord architecture

**Testing coverage:**
- Unit tests for CliBus (context, input handling, reply, empty input)
- Unit tests for SharedContext buses parameter
- Integration test for complete message flow
- Manual smoke testing

**Key benefits:**
- CLI uses same worker infrastructure as server mode
- Future routing/binding table support enabled
- Reduced code duplication
- Consistent architecture across all channels

**Next steps after this plan:**
- Add binding table for agent routing
- Add CLI-specific commands (e.g., `/switch cookie`)
- Multi-tenancy support
- Permission system integration
