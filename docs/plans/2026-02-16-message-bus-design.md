# Message Bus Design

**Date:** 2026-02-16
**Status:** Approved
**Scope:** Add real-time messaging platform support (Telegram, Discord) to pickle-bot

## Overview

Extend pickle-bot to support continuous conversation via messaging platforms alongside the existing console interface. The system runs as a long-running server process, maintaining a single shared conversation session across all platforms.

### Key Features

- Event-driven message bus runs alongside cron executor
- Single shared conversation session across Telegram, Discord, and console
- Response routing: reply to sender's platform for user messages
- Cron job responses route to configured default platform
- Frontend abstraction refactored to pure display (no input methods)

### Scope Constraints

- Personal use (2 users max), no concurrency requirements
- Continuous conversation with sliding window (existing AgentSession)
- Skip transient messages (only send final responses)

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Server Process                      │
│                                                          │
│  ┌──────────────────┐      ┌─────────────────────────┐ │
│  │  CronExecutor    │      │  MessageBusExecutor     │ │
│  │                  │      │                         │ │
│  │  - Runs cron jobs│      │  - Manages message queue│ │
│  │  - Sends to      │      │  - Processes sequentially│ │
│  │    default_      │      │  - Routes responses     │ │
│  │    platform      │      │                         │ │
│  └──────────────────┘      └─────────────────────────┘ │
│                                     │                    │
│                                     │                    │
│                           ┌─────────▼──────────┐        │
│                           │  AgentSession      │        │
│                           │  (Shared)          │        │
│                           │  - Sliding window  │        │
│                           │  - HistoryStore    │        │
│                           └────────────────────┘        │
│                                     │                    │
└─────────────────────────────────────┼────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
            ┌───────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
            │ TelegramBus  │  │ DiscordBus  │  │ (Future)    │
            └──────────────┘  └─────────────┘  └─────────────┘
```

### Data Flow

**User Message Flow:**
```
1. User sends "What's the weather?" on Telegram
2. TelegramBus receives → calls on_message("What's the weather?", "telegram", "chat_123")
3. MessageBusExecutor enqueues message
4. Worker processes message:
   - session.chat("What's the weather?", MessageBusFrontend())
   - AgentSession processes with LLM, tools, etc.
   - Returns "The weather is sunny"
5. MessageBusExecutor routes response:
   - bus_map["telegram"].send_message("chat_123", "The weather is sunny")
6. User receives response on Telegram
```

**Cron Job Flow:**
```
1. CronExecutor triggers at scheduled time
2. session.chat(prompt, SilentFrontend())
3. AgentSession processes, returns response
4. CronExecutor sends to default_platform:
   - config.messagebus.default_platform = "telegram"
   - bus.send_message(user_id, response)
```

## Core Components

### 1. MessageBus Abstraction

```python
# src/picklebot/messagebus/base.py
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

class MessageBus(ABC):
    """Abstract base for messaging platforms."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Platform identifier (e.g., 'telegram', 'discord')."""
        pass

    @abstractmethod
    async def start(self, on_message: Callable[[str, str, str], Awaitable[None]]) -> None:
        """
        Start listening for messages.

        Args:
            on_message: Callback async function(message: str, platform: str, user_id: str)
        """
        pass

    @abstractmethod
    async def send_message(self, user_id: str, content: str) -> None:
        """Send message to specific user on this platform."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and cleanup resources."""
        pass
```

### 2. Platform Implementations

**TelegramBus** (`src/picklebot/messagebus/telegram_bus.py`):
- Uses `python-telegram-bot` library
- `user_id` = Telegram chat_id
- Polling mode for simplicity

**DiscordBus** (`src/picklebot/messagebus/discord_bus.py`):
- Uses `discord.py` library
- `user_id` = Discord channel_id
- Listens to DMs or specific channel (configurable)

### 3. MessageBusExecutor

```python
# src/picklebot/core/messagebus_executor.py
class MessageBusExecutor:
    """Orchestrates message flow between platforms and agent."""

    def __init__(self, context: SharedContext, buses: list[MessageBus]):
        self.context = context
        self.buses = buses
        self.bus_map = {bus.platform_name: bus for bus in buses}

        # Single shared session for all platforms
        self.agent_def = context.agent_loader.load(context.config.default_agent)
        self.agent = Agent(agent_def, context)
        self.session = agent.new_session()

        # Message queue for sequential processing
        self.message_queue: asyncio.Queue[tuple[str, str, str]] = asyncio.Queue()
        self.frontend = MessageBusFrontend()

    async def run(self) -> None:
        """Start message processing loop and all buses."""
        # Start worker task to process messages
        worker_task = asyncio.create_task(self._process_messages())

        # Start all message buses
        bus_tasks = [
            bus.start(self._enqueue_message)
            for bus in self.buses
        ]

        try:
            await asyncio.gather(worker_task, *bus_tasks)
        except asyncio.CancelledError:
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    async def _enqueue_message(self, message: str, platform: str, user_id: str) -> None:
        """Add incoming message to queue (called by buses)."""
        await self.message_queue.put((message, platform, user_id))

    async def _process_messages(self) -> None:
        """Worker that processes messages sequentially from queue."""
        while True:
            message, platform, user_id = await self.message_queue.get()

            try:
                response = await self.session.chat(message, self.frontend)
                await self.bus_map[platform].send_message(user_id, response)
            except Exception as e:
                logger.error(f"Error processing message from {platform}: {e}")
                await self.bus_map[platform].send_message(
                    user_id,
                    "Sorry, I encountered an error processing your message."
                )
            finally:
                self.message_queue.task_done()
```

### 4. Refactored Frontend

**Pure Display Interface:**

```python
# src/picklebot/frontend/base.py
class Frontend(ABC):
    """Pure display interface - no input methods."""

    @abstractmethod
    def show_message(self, content: str) -> None:
        """Display a message (user or agent)."""
        pass

    @abstractmethod
    def show_system_message(self, content: str) -> None:
        """Display system-level message."""
        pass

    @abstractmethod
    @contextlib.contextmanager
    def show_transient(self, content: str) -> Iterator[None]:
        """Display transient message (tool calls, intermediate steps)."""
        yield
```

**MessageBusFrontend:**
- Silent implementation (no actual display)
- Used by MessageBusExecutor
- Transients are skipped (already in SilentFrontend)

**ConsoleFrontend Changes:**
- Remove `get_user_input()` method
- `show_message()` displays generic messages
- ChatLoop handles "You:" / "Agent:" formatting and console.input()

## Configuration

### Config Structure

```yaml
# ~/.pickle-bot/config.user.yaml
messagebus:
  enabled: true
  default_platform: "telegram"  # Required when enabled

  telegram:
    bot_token: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    enabled: true

  discord:
    bot_token: "your-discord-bot-token"
    channel_id: "123456789"  # Optional: restrict to specific channel
    enabled: true
```

### Config Model

```python
# src/picklebot/utils/config.py
class MessageBusConfig(BaseModel):
    enabled: bool = False
    default_platform: str | None = None
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None

    def model_post_init(self) -> None:
        """Validate default_platform is configured when enabled."""
        if self.enabled:
            # default_platform is required when enabled
            if not self.default_platform:
                raise ValueError("default_platform is required when messagebus is enabled")

            # Verify default_platform has valid config
            if self.default_platform == "telegram" and not self.telegram:
                raise ValueError("default_platform is 'telegram' but telegram config is missing")
            if self.default_platform == "discord" and not self.discord:
                raise ValueError("default_platform is 'discord' but discord config is missing")
            if self.default_platform not in ["telegram", "discord"]:
                raise ValueError(f"Invalid default_platform: {self.default_platform}")

class TelegramConfig(BaseModel):
    enabled: bool = True
    bot_token: str

class DiscordConfig(BaseModel):
    enabled: bool = True
    bot_token: str
    channel_id: str | None = None

class Config(BaseModel):
    # ... existing fields
    messagebus: MessageBusConfig = MessageBusConfig()
```

### Server Integration

```python
# src/picklebot/cli/server.py
async def server_command(ctx: typer.Context) -> None:
    config = ctx.obj.get("config")
    context = SharedContext(config)

    tasks = []

    # Cron executor (always runs)
    cron_executor = CronExecutor(context)
    tasks.append(cron_executor.run())

    # Message bus executor (if enabled)
    if config.messagebus.enabled:
        buses = create_buses_from_config(config)
        messagebus_executor = MessageBusExecutor(context, buses)
        tasks.append(messagebus_executor.run())

    await asyncio.gather(*tasks)
```

## Error Handling

### Platform Connection Failures

- **Strategy:** Fail fast on server startup
- If platform is enabled but can't connect, crash server with clear error
- Better to know immediately than run with broken platform

### Message Processing Failures

- **Strategy:** Catch errors, log, send user-friendly message
- Don't crash server for transient failures
- Example: LLM API timeout, tool execution error

### Rate Limiting

- **Strategy:** Use asyncio.Queue for sequential processing
- Messages queue naturally while processing
- No explicit "I'm busy" message needed

### Platform-Specific Errors

- **Strategy:** Platform implementations handle own retry logic
- Exponential backoff for rate limits
- After max retries, bubble error to MessageBusExecutor

### Server Shutdown

- Gracefully stop all platforms
- Cleanup resources (webhooks, connections)

## Session Management

### Shared Session

- One `AgentSession` instance in `MessageBusExecutor`
- All platforms write to same session
- History managed by AgentSession's sliding window (max 50 messages)
- Persists via existing `HistoryStore`
- Survives server restart (can resume from history)

### Console Session

- ChatLoop creates its own session (separate from message bus)
- Different use case: interactive console vs async message bus
- No shared state between console and message bus sessions

## Testing Strategy

### Unit Tests

**MessageBusExecutor Queue Logic:**
- Test messages process in order
- Test error handling doesn't break queue
- Test queue processes sequentially

### Manual Testing Checklist

**Telegram:**
- [ ] Start server with Telegram config
- [ ] Send message to bot from phone
- [ ] Verify response arrives on Telegram
- [ ] Send multiple messages rapidly (verify queue processing)
- [ ] Stop server (Ctrl+C), verify graceful shutdown

**Discord:**
- [ ] Start server with Discord config
- [ ] Send DM to bot
- [ ] Verify response arrives on Discord
- [ ] Test with specific channel configured

**Both Platforms:**
- [ ] Enable both Telegram and Discord
- [ ] Send message from Telegram, verify response on Telegram only
- [ ] Send message from Discord, verify response on Discord only
- [ ] Verify shared conversation history (ask "what did I just say?" from other platform)

**Cron Integration:**
- [ ] Create cron job with messagebus enabled
- [ ] Verify cron response goes to default_platform

**Configuration Validation:**
- [ ] Enable messagebus without default_platform → verify error
- [ ] Set default_platform to "telegram" without telegram config → verify error

## Implementation Notes

### Dependencies to Add

```toml
# pyproject.toml
dependencies = [
  # ... existing
  "python-telegram-bot>=20.0",
  "discord.py>=2.0",
]
```

### File Structure

```
src/picklebot/
├── messagebus/
│   ├── __init__.py
│   ├── base.py           # MessageBus abstract class
│   ├── telegram_bus.py   # Telegram implementation
│   └── discord_bus.py    # Discord implementation
├── core/
│   ├── messagebus_executor.py  # New file
│   └── ...
├── frontend/
│   ├── base.py           # Refactored (remove get_user_input)
│   └── console.py        # Updated
└── cli/
    └── server.py         # Updated to include MessageBusExecutor
```

### Migration Path

1. Refactor Frontend interface (breaking change, update ConsoleFrontend)
2. Update ChatLoop to handle input directly
3. Add messagebus module
4. Add MessageBusExecutor
5. Update server.py
6. Add config support
7. Add tests
