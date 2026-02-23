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
- `core/agent.py` - Main orchestrator
- `core/session.py` - Runtime state + history
- `core/context.py` - SharedContext for dependency injection
- `api/app.py` - FastAPI application factory
- `api/routers/` - REST endpoints for resources
- `workers/server.py` - Worker orchestration
- `tools/registry.py` - Tool registration
- `messagebus/base.py` - Platform abstraction
- `utils/def_loader.py` - Definition file parsing/writing

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

### HTTP API

FastAPI-based REST API for SDK-like access. Routers use `SharedContext` via dependency injection:

```python
from picklebot.api.deps import get_context
from picklebot.core.context import SharedContext

@router.get("/{agent_id}")
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)):
    return ctx.agent_loader.load(agent_id)
```

**Endpoints:**
- `GET/POST/PUT/DELETE /agents/{id}` - Agent CRUD
- `GET/POST/PUT/DELETE /skills/{id}` - Skill CRUD
- `GET/POST/PUT/DELETE /crons/{id}` - Cron CRUD
- `GET/DELETE /sessions/{id}` - Session management (no POST - created by system)
- `GET/POST/PUT/DELETE /memories/{path}` - Memory file CRUD
- `GET/PATCH /config` - Config read/update

**Write definitions with YAML frontmatter:**
```python
from picklebot.utils.def_loader import write_definition

frontmatter = {"name": "My Agent", "temperature": 0.7}
write_definition("my-agent", frontmatter, "System prompt...", agents_path, "AGENT.md")
```

Enabled by default via `api.enabled: true` in config.

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

Two-layer merge: `config.user.yaml` <- `config.runtime.yaml`

- `config.user.yaml` - User configuration (required fields: `llm`, `default_agent`). Created by onboarding.
- `config.runtime.yaml` - Runtime state (optional, internal only, managed by application)

Use `set_user()` and `set_runtime()` methods to update config:

```python
ctx.config.set_user("default_agent", "cookie")
ctx.config.set_runtime("current_session_id", "abc123")
```

Paths are relative to workspace and auto-resolved:

```python
agents_path: Path = Path("agents")   # resolves to workspace/agents
skills_path: Path = Path("skills")   # resolves to workspace/skills
```

### Nested LLM Config

Agents can override any LLM setting via a nested `llm:` object in frontmatter:

```yaml
---
name: Code Reviewer
description: Reviews code for quality
llm:
  temperature: 0.3
  max_tokens: 8192
---
```

The `AgentLoader._merge_llm_config()` performs a shallow merge of agent overrides with global LLM defaults. Only specify fields you want to override.

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
