# Cron System Design

**Date:** 2026-02-15
**Status:** Approved

## Overview

Transform pickle-bot from a chat-only agent to a 24/7 agent with cron job execution. A new `server` command runs a foreground daemon that executes scheduled agent invocations.

## Architecture

```
src/picklebot/
├── core/
│   ├── cron_loader.py    # CronDef model + CronLoader class
│   └── cron_executor.py  # Execution loop + job runner
├── cli/
│   ├── main.py           # Register 'server' command
│   └── server.py         # 'picklebot server' implementation
└── utils/
    └── config.py         # Add crons_path

~/.pickle-bot/
├── crons/                 # Configurable via config.crons_path
│   └── [job-id]/
│       └── CRON.md
```

### Data Flow

```
picklebot server
    → CronExecutor loads jobs via CronLoader
    → Every 60 seconds: check schedules
    → Due job → create Agent with fresh session → run prompt → log result
```

## Components

### CronDef + CronLoader

**Location:** `src/picklebot/core/cron_loader.py`

```python
class CronDef(BaseModel):
    """Loaded cron job definition."""
    id: str                    # directory name
    name: str                  # from frontmatter
    agent: str                 # agent ID to invoke
    schedule: str              # cron expression (e.g., "*/15 * * * *")
    prompt: str                # markdown body

    class Config:
        extra = "forbid"


class CronMetadata(BaseModel):
    """Lightweight cron info for discovery."""
    id: str
    name: str
    agent: str
    schedule: str


class CronLoader:
    """Load and validate cron job definitions."""

    def __init__(self, crons_path: Path):
        self.crons_path = crons_path

    def discover_crons(self) -> list[CronMetadata]:
        """Scan crons directory, return lightweight metadata for all jobs."""

    def load_cron(self, cron_id: str) -> CronDef:
        """Load full cron definition by ID."""

    def validate_cron(self, cron_path: Path) -> bool:
        """Validate a CRON.md file."""
```

### CRON.md Format

```markdown
---
name: Inbox Check
agent: pickle
schedule: "*/15 * * * *"
---

Check my inbox and summarize unread messages.
```

**Validation Rules:**
- Required frontmatter: `name`, `agent`, `schedule`
- Schedule must be valid cron expression
- Minimum granularity: 5 minutes (enforced at load time)
- Graceful degradation: skip invalid jobs, log warnings

### CronExecutor

**Location:** `src/picklebot/core/cron_executor.py`

```python
class CronExecutor:
    """Executes cron jobs on schedule."""

    def __init__(self, context: SharedContext):
        self.context = context
        self.cron_loader = CronLoader(context.config.crons_path)

    async def run(self) -> None:
        """Main loop: check every minute, execute due jobs."""
        while True:
            await self._tick()
            await asyncio.sleep(60)

    async def _tick(self) -> None:
        """Check schedules and run due jobs."""
        jobs = self.cron_loader.discover_crons()
        due_job = self._find_due_job(jobs)

        if due_job:
            await self._run_job(due_job)

    async def _run_job(self, cron_def: CronDef) -> None:
        """Execute a single cron job."""
        try:
            agent_def = AgentLoader(...).load(cron_def.agent)
            agent = Agent(agent_def, self.context)

            async with AgentSession(...) as session:
                session.add_message(UserMessage(content=cron_def.prompt))
                await agent.run(session)
        except Exception as e:
            logger.error(f"Cron job {cron_def.id} failed: {e}")

    def _find_due_job(self, jobs: list[CronMetadata]) -> CronDef | None:
        """Find the first job that's due to run."""
        # Use croniter to check if schedule matches current time
```

### Server CLI Command

**Location:** `src/picklebot/cli/server.py`

```python
import asyncio
import typer
from picklebot.core.cron_executor import CronExecutor
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging

@app.command("server")
def server_command(
    workspace: Path = typer.Option(
        Path.home() / ".pickle-bot",
        "--workspace", "-w",
        help="Path to pickle-bot workspace"
    )
) -> None:
    """Start the 24/7 server for cron job execution."""
    config = Config.load(workspace)
    setup_logging(config)
    context = SharedContext(config)

    executor = CronExecutor(context)

    typer.echo("Starting pickle-bot server...")
    asyncio.run(executor.run())
```

**Usage:**
```bash
picklebot server              # Start server with default workspace
picklebot server -w /custom   # Custom workspace path
```

## Configuration

### Config Model Update

**Location:** `src/picklebot/utils/config.py`

```python
class Config(BaseModel):
    """Application configuration."""
    default_agent: str = "pickle"
    history_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "history")
    agents_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "agents")
    crons_path: Path = Field(default_factory=lambda: Path.home() / ".pickle-bot" / "crons")  # New
    llm: LLMConfig = Field(default_factory=LLMConfig)
```

### Default Directory Structure

```
~/.pickle-bot/
├── config.system.yaml
├── agents/
│   └── [agent-name]/AGENT.md
├── crons/                    # New
│   └── [job-id]/CRON.md
└── history/
    └── sessions/
```

### User Override Example

```yaml
# ~/.pickle-bot/config.user.yaml
crons_path: /custom/path/to/crons
```

## Key Behaviors

| Aspect | Behavior |
|--------|----------|
| Scheduling | Homebrew asyncio loop, check every 60 seconds |
| Execution | Sequential (one job at a time via `await`) |
| Minimum granularity | 5 minutes (enforced at load time) |
| Session | Fresh session per run, no memory between runs |
| History | Use existing logging infrastructure |
| Errors | Log and continue |
| Server mode | Foreground daemon, Ctrl+C to stop |

## Dependencies

- `croniter` — For parsing and evaluating cron expressions

```toml
# pyproject.toml
dependencies = [
  # ... existing
  "croniter>=1.0.0",
]
```

## Out of Scope (Future)

- **Cron CRUD tools** — Will be implemented via skill system
- **Job history persistence** — Structured run history
- **Retry with backoff** — Retry failed jobs
- **Notifications** — Email/webhook on failure
- **Daemon mode** — `--daemon` flag or systemd support

## Implementation Checklist

- [ ] Add `croniter` to dependencies in `pyproject.toml`
- [ ] Create `CronDef`, `CronMetadata`, `CronLoader` in `core/cron_loader.py`
- [ ] Create `CronExecutor` in `core/cron_executor.py`
- [ ] Add `crons_path` to `Config` model
- [ ] Create `server` CLI command in `cli/server.py`
- [ ] Register `server` command in `cli/main.py`
- [ ] Write unit tests for `CronLoader`
- [ ] Write unit tests for `CronExecutor`
- [ ] Update README with server usage
