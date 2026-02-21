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
- `workers/` - Server mode workers (AgentWorker, CronWorker, MessageBusWorker)

**Core Flow:**
```
Agent receives message -> loads tools -> calls LLM -> executes tool calls -> response
```

**Key Files:**
- `core/agent.py` - Main orchestrator
- `core/session.py` - Runtime state + history
- `workers/server.py` - Worker orchestration
- `tools/registry.py` - Tool registration
- `messagebus/base.py` - Platform abstraction

## Critical Patterns

### Worker Architecture

All workers inherit from `Worker` base class. Jobs flow through `asyncio.Queue` to AgentWorker for sequential execution.

```
MessageBusWorker/CronWorker -> Queue -> AgentWorker -> Execute
```

See [docs/architecture.md](docs/architecture.md) for details.

### Definition Loading

All definitions (agents, skills, crons) are loaded via loader classes:

```python
from picklebot.core.agent_loader import AgentLoader
from picklebot.utils.def_loader import DefNotFoundError, InvalidDefError

# Load single agent (config is a Config object)
loader = AgentLoader(config)
agent_def = loader.load("my-agent")

# Discover all agents
agents = loader.discover_agents()
```

Raises:
- `DefNotFoundError` - Definition folder/file doesn't exist
- `InvalidDefError` - Definition file is malformed

### Message Conversion

`HistoryMessage` <-> litellm `Message` conversion:

```python
# Message -> HistoryMessage (for persistence)
history_msg = HistoryMessage.from_message(message)

# HistoryMessage -> Message (for LLM context)
message = history_msg.to_message()
```

### Tool Registration

Use `@tool` decorator or inherit `BaseTool`. Registered in `ToolRegistry`, schemas auto-generated for LiteLLM.

```python
from picklebot.tools.base import tool

@tool(
    name="my_tool",
    description="Does something",
    parameters={"type": "object", "properties": {...}, "required": [...]},
)
async def my_tool(arg: str) -> str:
    return f"Result: {arg}"
```

### Config Loading

Deep merge: `config.system.yaml` (defaults) <- `config.user.yaml` (overrides)

Paths are relative to workspace and auto-resolved:

```python
agents_path: Path = Path("agents")   # resolves to workspace/agents
skills_path: Path = Path("skills")   # resolves to workspace/skills
```

## Key Conventions

- **Workers** - Single responsibility, communicate via queues, restart on crash
- **Sessions** - One per conversation, persisted to `~/.pickle-bot/history/`
- **Tools** - Async functions, return strings, registered at startup
- **MessageBus** - Platform-agnostic with typed context (TelegramContext, DiscordContext)
- **Errors** - Custom exceptions in `utils/def_loader.py`
- **Frontend** - Abstract interface, platform-specific implementations

## What Goes Where

- **Configuration details** -> [docs/configuration.md](docs/configuration.md)
- **Full feature docs** -> [docs/features.md](docs/features.md)
- **Component details** -> [docs/architecture.md](docs/architecture.md)
- **Extension guide** -> [docs/extending.md](docs/extending.md)
