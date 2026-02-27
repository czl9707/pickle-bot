# Slash Commands Design

REPL commands for session and agent management via `/`-prefixed handlers.

## Overview

Slash commands provide a way to interact with picklebot's configuration and state without invoking the LLM. They work across all frontends (MessageBus platforms) and execute immediately with direct replies.

## Scope (Initial Implementation)

Read-only commands only:
- `/help` - List available commands
- `/agent` - List all agents
- `/skills` - List all skills
- `/crons` - List all cron jobs

No agent switching, no mutations, no session management in this phase.

## Architecture

```
Message arrives (Telegram/Discord)
    → starts with "/"?
        → Yes: CommandRegistry.dispatch(cmd, ctx) → reply directly
        → No: Normal agent.chat() flow via job queue
```

## File Structure

```
src/picklebot/core/commands/
    __init__.py      # exports CommandRegistry
    base.py          # Command ABC, CommandResult dataclass
    registry.py      # CommandRegistry class
    handlers.py      # Built-in command implementations
```

## Key Interfaces

```python
# base.py
from dataclasses import dataclass
from abc import ABC, abstractmethod
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
    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        """Execute the command and return result."""
        pass

# registry.py
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

    def dispatch(self, input: str, ctx: SharedContext) -> CommandResult | None:
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

## Built-in Commands

| Command | Aliases | Action |
|---------|---------|--------|
| `/help` | `/?` | List all available commands |
| `/agent` | `/agents` | List all agents (id, name, model) |
| `/skills` | | List all skills (id, name) |
| `/crons` | | List all cron jobs (id, schedule) |

## Command Handler Implementations

```python
# handlers.py
from picklebot.core.commands.base import Command, CommandResult
from picklebot.core.context import SharedContext

class HelpCommand(Command):
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
    name = "agent"
    aliases = ["agents"]

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        agents = ctx.agent_loader.list_all()
        if not agents:
            return CommandResult(message="No agents configured.")

        lines = ["**Agents:**"]
        for agent in agents:
            lines.append(f"- `{agent.id}`: {agent.name} ({agent.llm})")
        return CommandResult(message="\n".join(lines))


class SkillsCommand(Command):
    name = "skills"

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        skills = ctx.skill_loader.list_all()
        if not skills:
            return CommandResult(message="No skills configured.")

        lines = ["**Skills:**"]
        for skill in skills:
            lines.append(f"- `{skill.id}`: {skill.name}")
        return CommandResult(message="\n".join(lines))


class CronsCommand(Command):
    name = "crons"

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        crons = ctx.cron_loader.list_all()
        if not crons:
            return CommandResult(message="No cron jobs configured.")

        lines = ["**Cron Jobs:**"]
        for cron in crons:
            lines.append(f"- `{cron.id}`: {cron.schedule}")
        return CommandResult(message="\n".join(lines))
```

## Integration

### MessageBusWorker

Modify `server/messagebus_worker.py`:

```python
from picklebot.core.commands import CommandRegistry

class MessageBusWorker(Worker):
    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        # ... existing init ...
        self.command_registry = CommandRegistry.with_builtins()

    def _create_callback(self, platform: str):
        async def callback(message: str, context: Any) -> None:
            try:
                bus = self.bus_map[platform]

                if not bus.is_allowed(context):
                    return

                # Check for slash command
                if message.startswith("/"):
                    result = self.command_registry.dispatch(message, self.context)
                    if result and result.message:
                        await bus.reply(result.message, context)
                    return

                # Existing agent dispatch flow...
                user_id = context.user_id
                session_id = self._get_or_create_session_id(platform, user_id)
                frontend = MessageBusFrontend(bus, context)
                job = Job(...)
                await self.context.agent_queue.put(job)

            except Exception as e:
                self.logger.error(f"Error: {e}")

        return callback
```

## Future Extensions

Not in initial scope but designed to support:
- `/agent:<id>` - Switch to agent (requires session state mutation)
- `/skills:<id>` - Show skill details
- `/crons:<id>` - Show cron details
- `/new` - Create fresh session
- `/context` - Show token usage
- `/compact` - Trigger context compaction
- Delete operations (`/skills:<id> delete`)

## References

- claw0 s03_sessions.py: `handle_repl_command()` function
