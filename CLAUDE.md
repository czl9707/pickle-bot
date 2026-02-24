# CLAUDE.md

Essential context for working in pickle-bot codebase.

## Commands

```bash
uv run picklebot chat              # Interactive chat with default agent
uv run picklebot chat -a cookie    # Use specific agent
uv run picklebot server            # Start server (crons + messagebus)
uv run pytest                      # Run tests
uv run black . && uv run ruff check .  # Format + lint
```

## Architecture Overview

**Entry Points:**
- `cli/` - Typer commands (chat, server)
- `api/` - FastAPI HTTP interface (routers for agents, skills, crons, sessions, memories, config)
- `workers/` - Server mode workers (AgentWorker, CronWorker, MessageBusWorker)

**Core Flow:**
```
Agent receives message -> loads tools -> calls LLM -> executes tool calls -> response
```

**Key Files:**
- `core/agent.py` - Agent orchestrator
- `core/session.py` - Runtime state
- `core/context.py` - SharedContext DI
- `api/app.py` - FastAPI factory
- `api/routers/` - REST endpoints
- `workers/server.py` - Worker orchestration
- `tools/registry.py` - Tool registration
- `messagebus/base.py` - Platform abstraction
- `utils/def_loader.py` - Definition parsing
- `provider/llm/base.py` - LLM provider base

## Key Conventions

- **Workers** - Single responsibility, communicate via queues
- **Sessions** - One per conversation, persisted to disk
- **Tools** - Async functions, return strings
- **MessageBus** - Platform-agnostic with typed contexts
- **Providers** - Auto-registering via `__init_subclass__`

## What Goes Where

- **Configuration** -> [docs/configuration.md](docs/configuration.md)
- **Features** -> [docs/features.md](docs/features.md)
- **Architecture & Internals** -> [docs/architecture.md](docs/architecture.md)
