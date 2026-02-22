# HTTP API Design

Expose pickle-bot resources via HTTP API for SDK-like access.

## Overview

Add a FastAPI-based HTTP interface that provides CRUD operations on all pickle-bot resources:
- Agents
- Skills
- Crons
- Sessions (history)
- Memories
- Config

The API is config-driven and runs as part of the `picklebot server` command.

## Module Structure

```
src/picklebot/api/
├── __init__.py           # Exports create_app()
├── app.py                # FastAPI factory, router registration
├── deps.py               # Dependency injection (get_context)
├── schemas.py            # Pydantic create/update request models
└── routers/
    ├── __init__.py
    ├── agents.py         # /agents CRUD
    ├── skills.py         # /skills CRUD
    ├── crons.py          # /crons CRUD
    ├── sessions.py       # /sessions CRUD
    ├── memories.py       # /memories CRUD
    └── config.py         # /config read/update
```

## API Endpoints

All resources follow RESTful conventions with ID in path:

### Agents `/agents`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agents` | List all agents |
| GET | `/agents/{id}` | Get agent definition |
| POST | `/agents/{id}` | Create agent |
| PUT | `/agents/{id}` | Update agent |
| DELETE | `/agents/{id}` | Delete agent |

### Skills `/skills`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills` | List all skills |
| GET | `/skills/{id}` | Get skill definition |
| POST | `/skills/{id}` | Create skill |
| PUT | `/skills/{id}` | Update skill |
| DELETE | `/skills/{id}` | Delete skill |

### Crons `/crons`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/crons` | List all cron jobs |
| GET | `/crons/{id}` | Get cron definition |
| POST | `/crons/{id}` | Create cron |
| PUT | `/crons/{id}` | Update cron |
| DELETE | `/crons/{id}` | Delete cron |

### Sessions `/sessions`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions` | List sessions |
| GET | `/sessions/{id}` | Get session with messages |
| DELETE | `/sessions/{id}` | Delete session |

### Memories `/memories`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/memories` | List memory files |
| GET | `/memories/{path}` | Get memory content |
| POST | `/memories/{path}` | Create memory |
| PUT | `/memories/{path}` | Update memory |
| DELETE | `/memories/{path}` | Delete memory |

### Config `/config`
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get current config |
| PATCH | `/config` | Update config fields |

## Schemas

Reuse existing models for responses. Use Pydantic's `create_model()` to derive Create models:

```python
from pydantic import BaseModel, create_model

def make_create_model(model_cls: type[BaseModel], exclude: set[str] = {"id"}) -> type[BaseModel]:
    """Derive a Create model from existing model, excluding specified fields."""
    fields = {}
    for name, field in model_cls.model_fields.items():
        if name in exclude:
            continue
        fields[name] = (field.annotation, field.default if field.has_default else ...)

    return create_model(f"{model_cls.__name__}Create", **fields)

# Derived models
SkillCreate = make_create_model(SkillDef)
CronCreate = make_create_model(CronDef)
MemoryCreate = make_create_model(HistoryMessage, exclude={"timestamp", "tool_calls", "tool_call_id"})

# Hand-written (flattened LLM config)
class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    allow_skills: bool = False

class ConfigUpdate(BaseModel):
    default_agent: str | None = None
    chat_max_history: int | None = None
    job_max_history: int | None = None
```

## Dependency Injection

Use existing `SharedContext` for all loaders:

```python
# deps.py
from fastapi import Depends, Request
from picklebot.core.context import SharedContext

def get_context(request: Request) -> SharedContext:
    return request.app.state.context
```

Routers use it:
```python
@router.get("/{agent_id}")
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)):
    return ctx.agent_loader.load(agent_id)
```

## Configuration

Add `ApiConfig` to existing config schema:

```python
# utils/config.py
class ApiConfig(BaseModel):
    """HTTP API configuration."""
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

class Config(BaseModel):
    # ... existing fields ...
    api: ApiConfig = Field(default_factory=ApiConfig)
```

Example `config.user.yaml`:
```yaml
api:
  enabled: true
  host: 127.0.0.1
  port: 8000
```

## Server Integration

API starts as part of `picklebot server` when enabled:

```python
# server/server.py
import asyncio
import uvicorn

from picklebot.api import create_app
from picklebot.core.context import SharedContext

class Server:
    def __init__(self, context: SharedContext):
        self.context = context
        self.config = context.config
        self.workers: list[Worker] = []
        self._api_task: asyncio.Task | None = None

    async def run(self) -> None:
        # Start workers (existing logic)
        # ...

        # Start API if enabled
        if self.config.api.enabled:
            self._api_task = asyncio.create_task(self._run_api())

    async def _run_api(self) -> None:
        app = create_app(self.context)
        config = uvicorn.Config(
            app,
            host=self.config.api.host,
            port=self.config.api.port
        )
        server = uvicorn.Server(config)
        await server.serve()
```

## App Factory

```python
# api/app.py
from fastapi import FastAPI

from picklebot.api.routers import agents, skills, crons, sessions, memories, config
from picklebot.core.context import SharedContext

def create_app(context: SharedContext) -> FastAPI:
    app = FastAPI(title="Pickle Bot API")
    app.state.context = context

    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(skills.router, prefix="/skills", tags=["skills"])
    app.include_router(crons.router, prefix="/crons", tags=["crons"])
    app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    app.include_router(memories.router, prefix="/memories", tags=["memories"])
    app.include_router(config.router, prefix="/config", tags=["config"])

    return app
```

## Dependencies

Add FastAPI and uvicorn to `pyproject.toml`:
- `fastapi`
- `uvicorn[standard]`

## Out of Scope

- Chat/completions endpoint (may add websocket later)
- Authentication/authorization
- Rate limiting
- Pagination (sessions list may need this later)
