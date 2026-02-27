# Slash Commands Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add slash commands (`/help`, `/agent`, `/skills`, `/crons`) that execute directly in MessageBus without invoking the LLM.

**Architecture:** Command registry pattern in `core/commands/` with `Command` ABC, `CommandResult` dataclass, and `CommandRegistry` class. MessageBusWorker intercepts `/`-prefixed messages and dispatches to registry before agent queue.

**Tech Stack:** Python dataclasses, ABC, existing loaders (AgentLoader, SkillLoader, CronLoader)

---

## Task 1: Create base.py with CommandResult and Command ABC

**Files:**
- Create: `src/picklebot/core/commands/__init__.py`
- Create: `src/picklebot/core/commands/base.py`
- Create: `tests/core/commands/__init__.py`
- Create: `tests/core/commands/test_base.py`

**Step 1: Write the failing test**

```python
# tests/core/commands/test_base.py
"""Tests for command base classes."""

import pytest
from picklebot.core.commands.base import CommandResult, Command


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_default_values(self):
        """CommandResult should have None as default message."""
        result = CommandResult()
        assert result.message is None

    def test_with_message(self):
        """CommandResult can be created with a message."""
        result = CommandResult(message="Hello")
        assert result.message == "Hello"


class ConcreteCommand(Command):
    """Concrete implementation for testing."""

    name = "test"
    aliases = ["t", "tst"]

    def execute(self, args: str, ctx) -> CommandResult:
        return CommandResult(message=f"executed with: {args}")


class TestCommand:
    """Tests for Command ABC."""

    def test_command_has_name(self):
        """Command should have a name attribute."""
        cmd = ConcreteCommand()
        assert cmd.name == "test"

    def test_command_has_aliases(self):
        """Command should have aliases attribute."""
        cmd = ConcreteCommand()
        assert cmd.aliases == ["t", "tst"]

    def test_execute_returns_result(self):
        """execute() should return CommandResult."""
        cmd = ConcreteCommand()
        result = cmd.execute("arg1 arg2", None)
        assert isinstance(result, CommandResult)
        assert result.message == "executed with: arg1 arg2"
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/commands/test_base.py -v
```
Expected: FAIL with "No module named 'picklebot.core.commands'"

**Step 3: Create directory and __init__.py**

```bash
mkdir -p src/picklebot/core/commands tests/core/commands
touch src/picklebot/core/commands/__init__.py tests/core/commands/__init__.py
```

**Step 4: Write base.py implementation**

```python
# src/picklebot/core/commands/base.py
"""Base classes for slash commands."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


@dataclass
class CommandResult:
    """Result of executing a slash command."""
    message: str | None = None


class Command(ABC):
    """Base class for slash commands."""

    name: str
    aliases: list[str] = []

    @abstractmethod
    def execute(self, args: str, ctx: "SharedContext") -> CommandResult:
        """Execute the command and return result."""
        pass
```

**Step 5: Update __init__.py to export base classes**

```python
# src/picklebot/core/commands/__init__.py
"""Slash commands module."""

from picklebot.core.commands.base import Command, CommandResult

__all__ = ["Command", "CommandResult"]
```

**Step 6: Run test to verify it passes**

```bash
uv run pytest tests/core/commands/test_base.py -v
```
Expected: PASS

**Step 7: Commit**

```bash
git add src/picklebot/core/commands/ tests/core/commands/
git commit -m "feat(commands): add CommandResult and Command base class"
```

---

## Task 2: Create registry.py with CommandRegistry

**Files:**
- Modify: `src/picklebot/core/commands/__init__.py`
- Create: `src/picklebot/core/commands/registry.py`
- Create: `tests/core/commands/test_registry.py`

**Step 1: Write the failing test**

```python
# tests/core/commands/test_registry.py
"""Tests for CommandRegistry."""

import pytest
from picklebot.core.commands.base import Command, CommandResult
from picklebot.core.commands.registry import CommandRegistry


class MockCommand(Command):
    """Mock command for testing."""
    name = "mock"
    aliases = ["m"]

    def execute(self, args: str, ctx) -> CommandResult:
        return CommandResult(message=f"mock: {args}")


class MockCommand2(Command):
    """Another mock command."""
    name = "other"
    aliases = ["o", "alt"]

    def execute(self, args: str, ctx) -> CommandResult:
        return CommandResult(message=f"other: {args}")


class TestCommandRegistry:
    """Tests for CommandRegistry."""

    def test_register_command(self):
        """register() should add command by name."""
        registry = CommandRegistry()
        cmd = MockCommand()

        registry.register(cmd)

        assert registry._commands["mock"] == cmd

    def test_register_command_aliases(self):
        """register() should add command under all aliases."""
        registry = CommandRegistry()
        cmd = MockCommand()

        registry.register(cmd)

        assert registry._commands["m"] == cmd

    def test_resolve_non_command_returns_none(self):
        """resolve() should return None for non-slash input."""
        registry = CommandRegistry()

        result = registry.resolve("hello world")

        assert result is None

    def test_resolve_without_slash_prefix_returns_none(self):
        """resolve() should return None if no slash prefix."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = registry.resolve("mock")

        assert result is None

    def test_resolve_unknown_command_returns_none(self):
        """resolve() should return None for unknown command."""
        registry = CommandRegistry()

        result = registry.resolve("/unknown")

        assert result is None

    def test_resolve_known_command(self):
        """resolve() should return (command, args) for known command."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/mock")

        assert result == (cmd, "")

    def test_resolve_with_args(self):
        """resolve() should split command and args."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/mock arg1 arg2")

        assert result == (cmd, "arg1 arg2")

    def test_resolve_by_alias(self):
        """resolve() should work with aliases."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/m test")

        assert result == (cmd, "test")

    def test_resolve_case_insensitive(self):
        """resolve() should be case insensitive."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/MOCK")

        assert result == (cmd, "")

    def test_dispatch_returns_none_for_non_command(self):
        """dispatch() should return None for non-slash input."""
        registry = CommandRegistry()

        result = registry.dispatch("hello", None)

        assert result is None

    def test_dispatch_executes_command(self):
        """dispatch() should execute command and return result."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = registry.dispatch("/mock test", None)

        assert result.message == "mock: test"

    def test_dispatch_unknown_returns_none(self):
        """dispatch() should return None for unknown command."""
        registry = CommandRegistry()

        result = registry.dispatch("/unknown", None)

        assert result is None


class TestCommandRegistryWithBuiltins:
    """Tests for with_builtins factory (will pass after handlers implemented)."""

    def test_with_builtins_placeholder(self):
        """Placeholder - with_builtins tested after handlers exist."""
        # This test is replaced in Task 4
        pass
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/commands/test_registry.py -v
```
Expected: FAIL with "No module named 'picklebot.core.commands.registry'"

**Step 3: Write registry.py implementation**

```python
# src/picklebot/core/commands/registry.py
"""Command registry for managing slash commands."""

from typing import TYPE_CHECKING

from picklebot.core.commands.base import Command, CommandResult

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class CommandRegistry:
    """Registry for slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        """Register a command and its aliases."""
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def resolve(self, input: str) -> tuple[Command, str] | None:
        """
        Parse input and return (command, args) if it matches.

        Args:
            input: Full input string (e.g., "/agent" or "/help")

        Returns:
            Tuple of (Command, args_string) or None if no match
        """
        if not input.startswith("/"):
            return None

        parts = input[1:].split(None, 1)
        if not parts:
            return None

        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = self._commands.get(cmd_name)
        if cmd:
            return (cmd, args)
        return None

    def dispatch(self, input: str, ctx: "SharedContext") -> CommandResult | None:
        """
        Parse and execute a slash command.

        Args:
            input: Full input string
            ctx: SharedContext for accessing loaders

        Returns:
            CommandResult if command matched, None if not a command
        """
        resolved = self.resolve(input)
        if not resolved:
            return None

        cmd, args = resolved
        return cmd.execute(args, ctx)

    @classmethod
    def with_builtins(cls) -> "CommandRegistry":
        """Create registry with built-in commands registered."""
        from picklebot.core.commands.handlers import (
            HelpCommand,
            AgentCommand,
            SkillsCommand,
            CronsCommand,
        )

        registry = cls()
        registry.register(HelpCommand())
        registry.register(AgentCommand())
        registry.register(SkillsCommand())
        registry.register(CronsCommand())
        return registry
```

**Step 4: Update __init__.py to export CommandRegistry**

```python
# src/picklebot/core/commands/__init__.py
"""Slash commands module."""

from picklebot.core.commands.base import Command, CommandResult
from picklebot.core.commands.registry import CommandRegistry

__all__ = ["Command", "CommandResult", "CommandRegistry"]
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/core/commands/test_registry.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/core/commands/ tests/core/commands/
git commit -m "feat(commands): add CommandRegistry with register, resolve, dispatch"
```

---

## Task 3: Create handlers.py with built-in commands

**Files:**
- Create: `src/picklebot/core/commands/handlers.py`
- Create: `tests/core/commands/test_handlers.py`

**Step 1: Write the failing test**

```python
# tests/core/commands/test_handlers.py
"""Tests for built-in command handlers."""

import pytest

from picklebot.core.commands.base import CommandResult
from picklebot.core.commands.handlers import (
    HelpCommand,
    AgentCommand,
    SkillsCommand,
    CronsCommand,
)


class TestHelpCommand:
    """Tests for HelpCommand."""

    def test_name(self):
        """HelpCommand name should be 'help'."""
        cmd = HelpCommand()
        assert cmd.name == "help"

    def test_aliases(self):
        """HelpCommand should have '?' alias."""
        cmd = HelpCommand()
        assert "?" in cmd.aliases

    def test_execute_returns_available_commands(self):
        """execute() should list available commands."""
        cmd = HelpCommand()
        result = cmd.execute("", None)

        assert isinstance(result, CommandResult)
        assert "/help" in result.message
        assert "/agent" in result.message
        assert "/skills" in result.message
        assert "/crons" in result.message


class TestAgentCommand:
    """Tests for AgentCommand."""

    def test_name(self):
        """AgentCommand name should be 'agent'."""
        cmd = AgentCommand()
        assert cmd.name == "agent"

    def test_aliases(self):
        """AgentCommand should have 'agents' alias."""
        cmd = AgentCommand()
        assert "agents" in cmd.aliases

    def test_execute_no_agents(self, test_context):
        """execute() should show message when no agents configured."""
        cmd = AgentCommand()
        result = cmd.execute("", test_context)

        assert "No agents configured" in result.message

    def test_execute_with_agents(self, test_context, temp_agents_dir):
        """execute() should list agents."""
        # Create a test agent
        agent_dir = temp_agents_dir / "test-bot"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text("""---
name: Test Bot
---
You are a test bot.
""")

        cmd = AgentCommand()
        result = cmd.execute("", test_context)

        assert "test-bot" in result.message
        assert "Test Bot" in result.message


class TestSkillsCommand:
    """Tests for SkillsCommand."""

    def test_name(self):
        """SkillsCommand name should be 'skills'."""
        cmd = SkillsCommand()
        assert cmd.name == "skills"

    def test_execute_no_skills(self, test_context):
        """execute() should show message when no skills configured."""
        cmd = SkillsCommand()
        result = cmd.execute("", test_context)

        assert "No skills configured" in result.message


class TestCronsCommand:
    """Tests for CronsCommand."""

    def test_name(self):
        """CronsCommand name should be 'crons'."""
        cmd = CronsCommand()
        assert cmd.name == "crons"

    def test_execute_no_crons(self, test_context):
        """execute() should show message when no crons configured."""
        cmd = CronsCommand()
        result = cmd.execute("", test_context)

        assert "No cron jobs configured" in result.message
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/commands/test_handlers.py -v
```
Expected: FAIL with "No module named 'picklebot.core.commands.handlers'"

**Step 3: Write handlers.py implementation**

```python
# src/picklebot/core/commands/handlers.py
"""Built-in slash command handlers."""

from picklebot.core.commands.base import Command, CommandResult
from picklebot.core.context import SharedContext


class HelpCommand(Command):
    """Show available commands."""

    name = "help"
    aliases = ["?"]

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        lines = [
            "**Available Commands:**",
            "`/help` - Show this message",
            "`/agent` - List all agents",
            "`/skills` - List all skills",
            "`/crons` - List all cron jobs",
        ]
        return CommandResult(message="\n".join(lines))


class AgentCommand(Command):
    """List all configured agents."""

    name = "agent"
    aliases = ["agents"]

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        agents = ctx.agent_loader.discover_agents()
        if not agents:
            return CommandResult(message="No agents configured.")

        lines = ["**Agents:**"]
        for agent in agents:
            lines.append(f"- `{agent.id}`: {agent.name} ({agent.llm.model})")
        return CommandResult(message="\n".join(lines))


class SkillsCommand(Command):
    """List all configured skills."""

    name = "skills"

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        skills = ctx.skill_loader.discover_skills()
        if not skills:
            return CommandResult(message="No skills configured.")

        lines = ["**Skills:**"]
        for skill in skills:
            lines.append(f"- `{skill.id}`: {skill.name}")
        return CommandResult(message="\n".join(lines))


class CronsCommand(Command):
    """List all configured cron jobs."""

    name = "crons"

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        crons = ctx.cron_loader.discover_crons()
        if not crons:
            return CommandResult(message="No cron jobs configured.")

        lines = ["**Cron Jobs:**"]
        for cron in crons:
            lines.append(f"- `{cron.id}`: {cron.schedule}")
        return CommandResult(message="\n".join(lines))
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/core/commands/test_handlers.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/commands/handlers.py tests/core/commands/test_handlers.py
git commit -m "feat(commands): add HelpCommand, AgentCommand, SkillsCommand, CronsCommand"
```

---

## Task 4: Update registry test for with_builtins

**Files:**
- Modify: `tests/core/commands/test_registry.py`

**Step 1: Update test file with real with_builtins test**

Replace the placeholder test:

```python
# tests/core/commands/test_registry.py (replace TestCommandRegistryWithBuiltins class)

class TestCommandRegistryWithBuiltins:
    """Tests for with_builtins factory."""

    def test_with_builtins_creates_registry(self):
        """with_builtins() should create registry with all commands."""
        registry = CommandRegistry.with_builtins()

        assert registry._commands.get("help") is not None
        assert registry._commands.get("agent") is not None
        assert registry._commands.get("skills") is not None
        assert registry._commands.get("crons") is not None

    def test_with_builtins_includes_aliases(self):
        """with_builtins() should register aliases."""
        registry = CommandRegistry.with_builtins()

        assert registry._commands.get("?") is not None  # help alias
        assert registry._commands.get("agents") is not None  # agent alias

    def test_with_builtins_dispatch_help(self):
        """with_builtins() registry should dispatch /help."""
        registry = CommandRegistry.with_builtins()

        result = registry.dispatch("/help", None)

        assert result is not None
        assert "Available Commands" in result.message
```

**Step 2: Run test to verify it passes**

```bash
uv run pytest tests/core/commands/test_registry.py::TestCommandRegistryWithBuiltins -v
```
Expected: PASS

**Step 3: Commit**

```bash
git add tests/core/commands/test_registry.py
git commit -m "test(commands): add tests for CommandRegistry.with_builtins"
```

---

## Task 5: Integrate CommandRegistry into MessageBusWorker

**Files:**
- Modify: `src/picklebot/server/messagebus_worker.py`
- Modify: `tests/server/test_messagebus_worker.py`

**Step 1: Read existing test file**

```bash
cat tests/server/test_messagebus_worker.py
```

**Step 2: Write the failing test**

Add to `tests/server/test_messagebus_worker.py`:

```python
# Add to imports at top
from unittest.mock import AsyncMock, MagicMock
from picklebot.core.commands import CommandRegistry

# Add new test class
class TestMessageBusWorkerSlashCommands:
    """Tests for slash command handling in MessageBusWorker."""

    @pytest.fixture
    def mock_context(self, test_config):
        """Create mock context with minimal setup."""
        context = MagicMock(spec=SharedContext)
        context.config = test_config
        context.agent_loader = MagicMock()
        context.agent_loader.load.return_value = MagicMock(
            id="test", name="Test", system_prompt="test"
        )
        context.config.messagebus = MagicMock()
        context.config.messagebus.telegram = None
        context.config.messagebus.discord = None
        return context

    def test_worker_has_command_registry(self, mock_context):
        """MessageBusWorker should initialize CommandRegistry."""
        from picklebot.server.messagebus_worker import MessageBusWorker

        # Patch the buses to empty list
        mock_context.messagebus_buses = []

        worker = MessageBusWorker(mock_context)

        assert worker.command_registry is not None
        assert isinstance(worker.command_registry, CommandRegistry)

    @pytest.mark.anyio
    async def test_callback_handles_slash_command(self, mock_context):
        """Callback should dispatch slash commands and reply directly."""
        from picklebot.server.messagebus_worker import MessageBusWorker

        mock_context.messagebus_buses = []
        mock_context.agent_queue = AsyncMock()

        worker = MessageBusWorker(mock_context)

        # Create mock bus and context
        mock_bus = MagicMock()
        mock_bus.platform_name = "test"
        mock_bus.is_allowed.return_value = True
        mock_bus.reply = AsyncMock()

        mock_msg_context = MagicMock()
        mock_msg_context.user_id = "user123"

        # Get the callback
        callback = worker._create_callback("test")

        # Send slash command
        await callback("/help", mock_msg_context)

        # Should have replied directly
        mock_bus.reply.assert_called_once()
        call_args = mock_bus.reply.call_args[0][0]
        assert "Available Commands" in call_args

        # Should NOT have put job in queue
        mock_context.agent_queue.put.assert_not_called()
```

**Step 3: Run test to verify it fails**

```bash
uv run pytest tests/server/test_messagebus_worker.py::TestMessageBusWorkerSlashCommands -v
```
Expected: FAIL (no command_registry attribute, no slash handling)

**Step 4: Update messagebus_worker.py**

```python
# src/picklebot/server/messagebus_worker.py
# Add import at top:
from picklebot.core.commands import CommandRegistry

# In __init__, after self.bus_map line, add:
        self.command_registry = CommandRegistry.with_builtins()

# In _create_callback, after is_allowed check, add:
                # Check for slash command
                if message.startswith("/"):
                    result = self.command_registry.dispatch(message, self.context)
                    if result and result.message:
                        await bus.reply(result.message, context)
                    return
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/server/test_messagebus_worker.py::TestMessageBusWorkerSlashCommands -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/server/messagebus_worker.py tests/server/test_messagebus_worker.py
git commit -m "feat(messagebus): integrate CommandRegistry for slash command handling"
```

---

## Task 6: Run full test suite and fix any issues

**Step 1: Run all tests**

```bash
uv run pytest -v
```

**Step 2: Run linters**

```bash
uv run black . && uv run ruff check .
```

**Step 3: Fix any issues found**

If tests fail or linters complain, fix the issues.

**Step 4: Final commit if fixes needed**

```bash
git add -A
git commit -m "fix: address test/lint issues"
```

---

## Summary

**Files Created:**
- `src/picklebot/core/commands/__init__.py`
- `src/picklebot/core/commands/base.py`
- `src/picklebot/core/commands/registry.py`
- `src/picklebot/core/commands/handlers.py`
- `tests/core/commands/__init__.py`
- `tests/core/commands/test_base.py`
- `tests/core/commands/test_registry.py`
- `tests/core/commands/test_handlers.py`

**Files Modified:**
- `src/picklebot/server/messagebus_worker.py`
- `tests/server/test_messagebus_worker.py`
