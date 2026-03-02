# CLAUDE.md

Essential context for working in pickle-bot codebase.

## Commands

```bash
uv run picklebot chat              # Interactive chat with default agent
uv run picklebot chat -a cookie    # Use specific agent
uv run picklebot server            # Start server (crons + messagebus + API)
uv run pytest                      # Run tests
uv run black . && uv run ruff check .  # Format + lint
```

## Architecture Overview

**Event-Driven Architecture:**
```
EventBus (pub/sub) -> Workers subscribe to events -> Process -> Publish new events
```

**Workers (server mode):**
- `EventBus` - Central pub/sub event distribution with persistence
- `AgentWorker` - Subscribes to InboundEvent/DispatchEvent, runs agent chat
- `CronWorker` - Emits InboundEvent on schedule
- `MessageBusWorker` - Emits InboundEvent from platforms (Telegram, Discord)
- `DeliveryWorker` - Subscribes to OutboundEvent, delivers to platforms
- `WebSocketWorker` - Subscribes to events, streams to WebSocket clients

**Event Types (core/events.py):**
- `InboundEvent` - External work entering the system
- `OutboundEvent` - Agent responses to deliver
- `DispatchEvent` - Agent-to-agent delegation
- `DispatchResultEvent` - Results from dispatched agents

**EventSource Types:**
- `AgentEventSource`, `CronEventSource` (in core/events.py)
- `CliEventSource`, `TelegramEventSource`, `DiscordEventSource` (in messagebus/)

**Key Files:**
- `core/agent.py` - Agent orchestrator + AgentSession
- `core/events.py` - Event types + EventSource hierarchy
- `core/eventbus.py` - Pub/sub event distribution
- `core/context.py` - SharedContext DI container
- `core/routing.py` - Routes sources to agents
- `core/commands/` - Slash command system
- `server/server.py` - Worker orchestration
- `messagebus/` - Platform implementations (Telegram, Discord, CLI)

## Key Conventions

- **Events** - Typed dataclasses, serialized to JSON for persistence
- **Workers** - Subscribe to events via EventBus, single responsibility
- **EventSource** - Typed event origin with platform-specific data
- **Routing** - Regex bindings route sources to agents
- **Sessions** - One per conversation, persisted via HistoryStore
- **Tools** - Async functions, registered via ToolRegistry

## Project Structure

```
src/picklebot/
├── cli/                    # CLI commands
├── core/                   # Core domain logic
│   ├── agent.py           # Agent + AgentSession
│   ├── events.py          # Event types + EventSource
│   ├── eventbus.py        # Pub/sub distribution
│   ├── routing.py         # Source-to-agent routing
│   └── commands/          # Slash command system
├── server/                 # Server workers
│   ├── server.py          # Worker orchestration
│   ├── agent_worker.py    # Agent execution
│   ├── cron_worker.py     # Scheduled jobs
│   ├── delivery_worker.py # Message delivery
│   └── messagebus_worker.py # Platform ingestion
├── messagebus/            # Platform implementations
├── provider/              # LLM, web search, web read
├── tools/                 # Agent tools
├── api/                   # HTTP API
└── utils/                 # Config, logging, etc.
```

## What Goes Where

- **Configuration** -> [docs/configuration.md](docs/configuration.md)
- **Features** -> [docs/features.md](docs/features.md)
- **Architecture** -> [docs/architecture.md](docs/architecture.md)
