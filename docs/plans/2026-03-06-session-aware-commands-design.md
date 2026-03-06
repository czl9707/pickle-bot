# Session-Aware Slash Commands Design

**Date:** 2026-03-06
**Status:** Design Approved

## Problem

Current slash commands only have access to `SharedContext`, limiting them to read-only operations. We need commands that can:
- Trigger session compaction
- Display session information
- Switch agents for a channel
- Clear conversations

These operations require access to `AgentSession`.

## Solution

Move all command dispatch from `ChannelWorker` to `AgentWorker`, after session is loaded. Commands receive `AgentSession` which provides both session state and `shared_context`.

## Architecture Change

### Current Flow
```
ChannelWorker
    ↓ (check slash command)
CommandRegistry.dispatch(message, SharedContext)
    ↓ (if not command)
Create InboundEvent → AgentWorker → load session → chat
```

### New Flow
```
ChannelWorker
    ↓
Create InboundEvent → AgentWorker → load session
                            ↓ (check slash command)
                    CommandRegistry.dispatch(message, AgentSession)
                            ↓ (if not command)
                        chat with session
```

## Implementation

### 1. Update Command Base Class

**File:** `src/picklebot/core/commands/base.py`

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession


class Command(ABC):
    """Base class for slash commands."""

    name: str
    aliases: list[str] = []
    description: str = ""

    @abstractmethod
    def execute(self, args: str, session: "AgentSession") -> str:
        """Execute the command and return response string."""
        pass
```

**Changes:**
- `execute()` parameter changed from `ctx: SharedContext` to `session: AgentSession`
- Commands access shared resources via `session.shared_context`

### 2. Add RoutingTable Methods

**File:** `src/picklebot/core/routing.py`

Add two new methods to `RoutingTable`:

```python
def add_runtime_binding(self, source_pattern: str, agent_id: str) -> None:
    """
    Add a runtime routing binding.

    Args:
        source_pattern: Source pattern to match (e.g., "platform-telegram:user_123:chat_456")
        agent_id: Agent to route to
    """
    # Get existing runtime bindings
    bindings = self._context.config.routing.get("bindings", [])

    # Add new binding (exact match for source pattern)
    bindings.append({
        "agent": agent_id,
        "value": source_pattern
    })

    # Update runtime config
    self._context.config.set_runtime("routing.bindings", bindings)

    # Clear cache to force reload on next resolve
    self._bindings = None


def clear_session_cache(self, source_str: str) -> None:
    """
    Clear session cache for a source, forcing new session creation on next message.

    Args:
        source_str: Source string to clear (e.g., "platform-telegram:user_123:chat_456")
    """
    if source_str in self._context.config.sources:
        # Remove from sources dict
        del self._context.config.sources[source_str]

        # Persist to runtime config
        self._context.config.set_runtime("sources", self._context.config.sources)
```

### 3. Update Command Registry

**File:** `src/picklebot/core/commands/registry.py`

Update `dispatch()` signature:

```python
def dispatch(self, input: str, session: "AgentSession") -> str | None:
    """
    Parse and execute a slash command.

    Args:
        input: Full input string
        session: AgentSession with full context

    Returns:
        Response string if command matched, None if not a command
    """
    resolved = self.resolve(input)
    if not resolved:
        return None

    cmd, args = resolved
    return cmd.execute(args, session)
```

### 4. Update Existing Commands

**File:** `src/picklebot/core/commands/handlers.py`

Update all existing commands to use `session.shared_context`:

```python
class HelpCommand(Command):
    name = "help"
    aliases = ["?"]
    description = "Show available commands"

    def execute(self, args: str, session: AgentSession) -> str:
        lines = ["**Available Commands:**"]
        for cmd in session.shared_context.command_registry.list_commands():
            names = [f"/{cmd.name}"] + [f"/{a}" for a in cmd.aliases]
            lines.append(f"{', '.join(names)} - {cmd.description}")
        return "\n".join(lines)


class AgentCommand(Command):
    name = "agent"
    aliases = ["agents"]
    description = "Switch to a different agent (starts fresh session)"

    def execute(self, args: str, session: AgentSession) -> str:
        if not args:
            # List agents
            agents = session.shared_context.agent_loader.discover_agents()
            lines = ["**Agents:**"]
            for agent in agents:
                marker = " (current)" if agent.id == session.agent.agent_def.id else ""
                lines.append(f"- `{agent.id}`: {agent.name}{marker}")
            return "\n".join(lines)

        # Switch agent
        agent_id = args.strip()
        source_str = str(session.source)

        # Verify agent exists
        try:
            session.shared_context.agent_loader.load(agent_id)
        except ValueError:
            return f"✗ Agent `{agent_id}` not found."

        # Add runtime binding + clear cache
        routing = session.shared_context.routing_table
        routing.add_runtime_binding(source_str, agent_id)
        routing.clear_session_cache(source_str)

        return f"✓ Switched to `{agent_id}`. Next message starts fresh conversation."


class SkillsCommand(Command):
    name = "skills"
    description = "List all skills"

    def execute(self, args: str, session: AgentSession) -> str:
        skills = session.shared_context.skill_loader.discover_skills()
        if not skills:
            return "No skills configured."

        lines = ["**Skills:**"]
        for skill in skills:
            lines.append(f"- `{skill.id}`: {skill.description}")
        return "\n".join(lines)


class CronsCommand(Command):
    name = "crons"
    description = "List all cron jobs"

    def execute(self, args: str, session: AgentSession) -> str:
        crons = session.shared_context.cron_loader.discover_crons()
        if not crons:
            return "No cron jobs configured."

        lines = ["**Cron Jobs:**"]
        for cron in crons:
            lines.append(f"- `{cron.id}`: {cron.schedule}")
        return "\n".join(lines)
```

### 5. Add New Commands

**File:** `src/picklebot/core/commands/handlers.py`

Add these new command classes:

```python
class CompactCommand(Command):
    """Trigger manual context compaction."""

    name = "compact"
    description = "Compact conversation context manually"

    def execute(self, args: str, session: AgentSession) -> str:
        # Force compaction via context_guard
        session.state = await session.context_guard.check_and_compact(
            session.state, force=True
        )
        msg_count = len(session.state.messages)
        return f"✓ Context compacted. {msg_count} messages retained."


class ContextCommand(Command):
    """Show session context information."""

    name = "context"
    description = "Show session context information"

    def execute(self, args: str, session: AgentSession) -> str:
        lines = [
            f"**Session:** `{session.session_id}`",
            f"**Agent:** {session.agent.agent_def.name}",
            f"**Source:** `{session.source}`",
            f"**Messages:** {len(session.state.messages)}",
            f"**Tokens:** {session.context_guard.estimate_tokens(session.state):,}",
        ]
        return "\n".join(lines)


class ClearCommand(Command):
    """Clear conversation and start fresh."""

    name = "clear"
    description = "Clear conversation and start fresh"

    def execute(self, args: str, session: AgentSession) -> str:
        # Clear session cache (keeps session info, just resets for next message)
        source_str = str(session.source)
        session.shared_context.routing_table.clear_session_cache(source_str)

        return "✓ Conversation cleared. Next message starts fresh."


class SessionCommand(Command):
    """Show current session details."""

    name = "session"
    description = "Show current session details"

    def execute(self, args: str, session: AgentSession) -> str:
        info = session.shared_context.history_store.get_session_info(
            session.session_id
        )
        lines = [
            f"**Session ID:** `{session.session_id}`",
            f"**Agent:** {session.agent.agent_def.name} (`{session.agent.agent_def.id}`)",
            f"**Created:** {info.created_at}",
            f"**Messages:** {len(session.state.messages)}",
            f"**Source:** `{session.source}`",
        ]
        return "\n".join(lines)
```

Register new commands in `CommandRegistry.with_builtins()`:

```python
@classmethod
def with_builtins(cls) -> "CommandRegistry":
    """Create registry with built-in commands registered."""
    from picklebot.core.commands.handlers import (
        HelpCommand,
        AgentCommand,
        SkillsCommand,
        CronsCommand,
        CompactCommand,
        ContextCommand,
        ClearCommand,
        SessionCommand,
    )

    registry = cls()
    registry.register(HelpCommand())
    registry.register(AgentCommand())
    registry.register(SkillsCommand())
    registry.register(CronsCommand())
    registry.register(CompactCommand())
    registry.register(ContextCommand())
    registry.register(ClearCommand())
    registry.register(SessionCommand())
    return registry
```

### 6. Move Command Dispatch to AgentWorker

**File:** `src/picklebot/server/agent_worker.py`

Add command dispatch after session is loaded:

```python
async def _process_event(self, event: InboundEvent):
    """Process an inbound event."""
    agent = self.context.agent_loader.load(event.agent_id)
    session = agent.resume_or_create(event.session_id, event.source)

    # Check for slash command FIRST
    if event.content.startswith("/"):
        result = self.context.command_registry.dispatch(
            event.content, session
        )
        if result:
            # Emit OutboundEvent with command result
            await self.context.eventbus.publish(
                OutboundEvent(
                    session_id=session.session_id,
                    agent_id=agent.agent_def.id,
                    source=event.source,
                    content=result,
                    timestamp=time.time(),
                )
            )
            return  # Skip agent chat

    # Normal chat flow
    response = await session.chat(event.content)
    # ... emit OutboundEvent ...
```

### 7. Remove Command Dispatch from ChannelWorker

**File:** `src/picklebot/server/channel_worker.py`

Remove command dispatch logic:

```python
async def callback(message: str, source: EventSource) -> None:
    try:
        channel = self.channel_map[platform]

        if not channel.is_allowed(source):
            self.logger.debug(f"Ignored non-whitelisted message from {platform}")
            return

        # REMOVED: Command dispatch moved to AgentWorker

        # Set default delivery source only on first non-CLI platform message
        if source.is_platform and source.platform_name != "cli":
            if not self.context.config.default_delivery_source:
                source_str_value = str(source)
                self.context.config.set_runtime(
                    "default_delivery_source", source_str_value
                )
                self.context.config.default_delivery_source = source_str_value

        agent_id = self.context.routing_table.resolve(str(source))
        session_id = self.context.routing_table.get_or_create_session_id(
            source, agent_id
        )

        # Publish INBOUND event
        event = InboundEvent(
            session_id=session_id,
            agent_id=agent_id,
            source=source,
            content=message,
            timestamp=time.time(),
        )
        await self.context.eventbus.publish(event)
```

## Command Summary

| Command | Aliases | Description |
|---------|---------|-------------|
| `/help` | `/?` | Show available commands |
| `/agent [<id>]` | `/agents` | List agents or switch agent |
| `/skills` | | List all skills |
| `/crons` | | List all cron jobs |
| `/compact` | | Trigger manual compaction |
| `/context` | | Show session context info |
| `/clear` | | Clear conversation |
| `/session` | | Show session details |

## Benefits

1. **Single dispatch point** - All commands in AgentWorker, simpler flow
2. **Full context access** - Commands have both session state and shared resources
3. **EventBus ready** - Commands processed as part of normal event flow
4. **Type safe** - Commands always have session, no None checks needed
5. **Cleaner API** - `execute(args, session)` instead of multiple context objects

## Testing Strategy

1. **Unit tests for new RoutingTable methods:**
   - `test_add_runtime_binding()` - verify binding added and cache cleared
   - `test_clear_session_cache()` - verify source removed from cache

2. **Unit tests for new commands:**
   - Each command with various argument combinations
   - Verify correct response format
   - Verify side effects (routing changes, cache clears)

3. **Integration tests:**
   - End-to-end command dispatch via AgentWorker
   - Verify `/agent` switching creates new session on next message
   - Verify `/clear` starts fresh conversation

## Migration Path

1. Add new methods to `RoutingTable`
2. Update `Command` base class
3. Update existing command handlers
4. Add new command handlers
5. Update `CommandRegistry.with_builtins()`
6. Add dispatch to `AgentWorker`
7. Remove dispatch from `ChannelWorker`
8. Update all tests

## Notes

- `CompactCommand.execute()` needs to be async - commands may need async support
- `/agent` without args lists agents and marks current agent
- Session cache clearing preserves session history, just forces new session creation on next message
- Runtime bindings persist across restarts (stored in `config.runtime.yaml`)
