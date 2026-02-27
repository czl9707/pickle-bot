# CLI MessageBus Integration - Design Document

**Date:** 2026-02-26
**Status:** Approved
**Goal:** Unify CLI with MessageBus architecture to enable future routing capabilities and reduce code duplication

## Overview

Treat CLI as just another channel, unified with Telegram/Discord via MessageBus abstraction. This enables:
- Future routing/binding table support for CLI
- Unified architecture across all channels
- Reuse of MessageBusWorker and AgentDispatcherWorker infrastructure

## Architecture

```
stdin input
    │
    ▼
CliBus.run() reads stdin via asyncio.to_thread()
    │
    ▼
calls on_message(text, CliContext)
    │
    ▼
MessageBusWorker callback
    │
    ▼
creates session + MessageBusFrontend
    │
    ▼
Agent.chat() via MessageBusFrontend
    │
    ▼
CliBus.reply() prints to stdout via Rich
```

## Components

### 1. CliBus (`src/picklebot/messagebus/cli_bus.py`)

```python
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
        return True  # CLI always allowed

    async def reply(self, content: str, context: CliContext) -> None:
        """Print to stdout with Rich formatting."""
        self.console.print(content)

    async def post(self, content: str, target: str | None = None) -> None:
        """Post proactive message (same as reply for CLI)."""
        self.console.print(content)

    async def run(self, on_message: Callable[[str, CliContext], Awaitable[None]]) -> None:
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

    async def stop(self) -> None:
        """Stop the input loop."""
        self._stop_event.set()
```

**Key design decisions:**
- Uses `asyncio.to_thread()` to wrap synchronous `input()` in async context
- `reply()` prints to stdout via Rich console (same formatting as ConsoleFrontend)
- No welcome/goodbye messages - keeps it simple
- `user_id` hardcoded to "cli-user" for session management

### 2. SharedContext Modification (`src/picklebot/core/context.py`)

```python
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

**Key design decisions:**
- Optional `buses` parameter allows CLI to inject CliBus
- Backward compatible - existing code works unchanged
- Server mode loads from config, CLI mode injects explicit bus

### 3. ChatLoop Refactor (`src/picklebot/cli/chat.py`)

```python
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
```

**Key design decisions:**
- No longer creates own Agent or ConsoleFrontend
- Reuses MessageBusWorker and AgentDispatcherWorker
- Very similar to server.py pattern
- No welcome/goodbye - just starts processing input

### 4. MessageBusWorker - No Changes Needed!

```python
# Existing code works for CLI:
frontend = MessageBusFrontend(bus, context)  # Works for all platforms
await bus.reply(content, context)  # Telegram: API, Discord: API, CLI: stdout
```

MessageBusFrontend calls `bus.reply()` which handles platform-specific output:
- **Telegram:** Sends via Telegram API
- **Discord:** Sends via Discord API
- **CLI:** Prints to stdout via Rich

**No platform-specific branching needed!**

## Session Management

CLI sessions follow same pattern as other platforms:
- Platform: `"cli"`
- User ID: `"cli-user"`
- Session stored at: `messagebus.cli.sessions.cli-user`
- Session persists within single CLI run
- Each CLI run reuses same session ID

## Error Handling

### Input Handling
```python
try:
    while not self._stop_event.is_set():
        user_input = await asyncio.to_thread(input, "You: ")
        # ... process input
except (KeyboardInterrupt, EOFError):
    pass  # Graceful exit
```

### Graceful Shutdown
```python
try:
    await asyncio.gather(dispatcher.run(), message_bus.run())
except asyncio.CancelledError:
    await bus.stop()
    raise
```

### Config Validation
- Default agent existence validated at config load time
- No runtime agent-not-found errors possible

## Edge Cases

1. **Empty input** - Skipped via `if not user_input.strip(): continue`
2. **Multiple CLI sessions** - Each run has own SharedContext instance
3. **CLI runs while server running** - Independent processes, no conflict
4. **Very long input** - Handled by stdin, no special processing needed

## Testing Strategy

### Unit Tests

```python
# tests/messagebus/test_cli_bus.py

async def test_cli_bus_read_input():
    """Test CliBus reads input and calls callback."""
    bus = CliBus()
    messages = []

    async def capture(message: str, context: CliContext):
        messages.append(message)

    with patch('builtins.input', side_effect=["hello", "quit"]):
        await bus.run(capture)

    assert messages == ["hello"]

async def test_cli_bus_reply():
    """Test CliBus.reply() prints to stdout."""
    bus = CliBus()
    context = CliContext()

    with patch.object(bus.console, 'print') as mock_print:
        await bus.reply("test message", context)

    mock_print.assert_called_once_with("test message")

# tests/core/test_context.py

def test_shared_context_with_custom_buses():
    """Test SharedContext accepts custom bus list."""
    config = Config()
    cli_bus = CliBus()

    context = SharedContext(config, buses=[cli_bus])

    assert context.messagebus_buses == [cli_bus]
```

### Integration Tests

```python
# tests/cli/test_chat_integration.py

async def test_cli_chat_flow():
    """Test complete CLI message flow through workers."""
    config = create_test_config()
    bus = CliBus()
    context = SharedContext(config, buses=[bus])

    with patch('builtins.input', side_effect=["hello", "quit"]):
        dispatcher = AgentDispatcherWorker(context)
        message_bus = MessageBusWorker(context)

        task = asyncio.create_task(
            asyncio.gather(dispatcher.run(), message_bus.run())
        )
        await asyncio.sleep(0.5)
        task.cancel()

    # Verify session was created
    assert "cli-user" in config.messagebus.cli.sessions
```

## Implementation Checklist

- [ ] Create `src/picklebot/messagebus/cli_bus.py` with CliBus and CliContext
- [ ] Modify `src/picklebot/core/context.py` to accept optional `buses` parameter
- [ ] Refactor `src/picklebot/cli/chat.py` ChatLoop to use MessageBusWorker pattern
- [ ] Remove ConsoleFrontend usage from CLI (MessageBusFrontend handles it)
- [ ] Add unit tests for CliBus
- [ ] Add integration test for full CLI flow
- [ ] Update MessageBus.from_config() to include CliBus if needed (or leave as-is)

## Future Enhancements

Once this is implemented, future work can include:
- Binding table for routing CLI commands to different agents
- CLI-specific commands (e.g., `/switch cookie`)
- Multi-tenancy support
- Permission system integration

## References

- Original plan: `docs/plans/2026-02-26-cli-messagebus.md`
- claw0 s04_channels.py: `CLIChannel`, `InboundMessage` patterns
