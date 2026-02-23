# Agent Concurrency Architecture Design

Date: 2026-02-23

## Overview

Redesign the agent worker architecture to support per-agent concurrency control while maintaining message ordering and isolation between agents.

## Goals

- **Performance**: Allow multiple sessions per agent to run concurrently
- **Isolation**: Agent A at capacity should not block Agent B
- **Flexibility**: Each agent can scale independently via `max_concurrency` config

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Server                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────┐      ┌─────────────┐                      │
│   │ MessageBus  │      │  CronWorker │                      │
│   │   Worker    │      │             │                      │
│   └──────┬──────┘      └──────┬──────┘                      │
│          │                    │                              │
│          └──────────┬─────────┘                              │
│                     ▼                                        │
│            ┌─────────────────┐                               │
│            │  asyncio.Queue  │                               │
│            └────────┬────────┘                               │
│                     │                                        │
│                     ▼                                        │
│   ┌─────────────────────────────────────────────────────┐   │
│   │               AgentJobRouter (Worker)                │   │
│   │                                                      │   │
│   │  • semaphores: dict[agent_id, Semaphore]            │   │
│   │  • Pulls jobs sequentially from queue                │   │
│   │  • Lazy-loads AgentDef (no cache)                    │   │
│   │  • Creates SessionExecutor per job                   │   │
│   └──────────────────────┬──────────────────────────────┘   │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                 │
│        ▼                 ▼                 ▼                 │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐             │
│   │Executor │      │Executor │      │Executor │             │
│   │ Agent A │      │ Agent B │      │ Agent A │             │
│   │ Wait ↓  │      │ Running │      │ Wait ↓  │             │
│   └─────────┘      └─────────┘      └─────────┘             │
│                                                              │
│   (Semaphores ensure A#1 completes before A#2 starts)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Key Insight

Using `asyncio.Semaphore` per agent creates an **implicit per-agent queue** without actually managing multiple queues:

1. Router pulls jobs **sequentially** from shared queue → preserves global order
2. Each job becomes a task that waits on **its agent's semaphore**
3. Agent X at capacity → only X's tasks wait, Y's tasks flow through
4. When X's semaphore opens → next waiting X task proceeds (FIFO within agent)

## Components

### AgentJobRouter (Worker)

Replaces current `AgentWorker`. Routes jobs to session executors with per-agent concurrency control.

```python
class AgentJobRouter(Worker):
    """Routes jobs to session executors with per-agent concurrency control."""

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: SharedContext, agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def run(self) -> None:
        """Process jobs sequentially, dispatch to executors."""
        while True:
            job = await self.agent_queue.get()
            self._dispatch_job(job)
            self.agent_queue.task_done()
            self._maybe_cleanup_semaphores()

    def _dispatch_job(self, job: Job) -> None:
        """Create executor task for job."""
        agent_def = self.context.agent_loader.load(job.agent_id)
        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(
            SessionExecutor(self.context, agent_def, job, sem).run()
        )

    def _get_or_create_semaphore(self, agent_def: AgentDef) -> asyncio.Semaphore:
        if agent_def.id not in self._semaphores:
            self._semaphores[agent_def.id] = asyncio.Semaphore(
                agent_def.max_concurrency
            )
        return self._semaphores[agent_def.id]

    def _maybe_cleanup_semaphores(self) -> None:
        """Remove semaphores for deleted agents."""
        if len(self._semaphores) <= self.CLEANUP_THRESHOLD:
            return

        existing = {a.id for a in self.context.agent_loader.discover_agents()}
        stale = set(self._semaphores.keys()) - existing
        for agent_id in stale:
            del self._semaphores[agent_id]
            self.logger.debug(f"Cleaned up semaphore for deleted agent: {agent_id}")
```

### SessionExecutor

Executes a single agent session job. Waits on semaphore before execution.

```python
class SessionExecutor:
    """Executes a single agent session job."""

    def __init__(
        self,
        context: SharedContext,
        agent_def: AgentDef,
        job: Job,
        semaphore: asyncio.Semaphore,
    ):
        self.context = context
        self.agent_def = agent_def
        self.job = job
        self.semaphore = semaphore
        self.logger = logging.getLogger(f"{__name__}.{agent_def.id}")

    async def run(self) -> None:
        """Wait for semaphore, execute session, release."""
        async with self.semaphore:
            await self._execute()

    async def _execute(self) -> None:
        """Run the actual agent session."""
        try:
            agent = Agent(self.agent_def, self.context)

            if self.job.session_id:
                try:
                    session = agent.resume_session(self.job.session_id)
                except ValueError:
                    session = agent.new_session(self.job.mode, session_id=self.job.session_id)
            else:
                session = agent.new_session(self.job.mode)

            await session.chat(self.job.message, self.job.frontend)
            self.logger.info(f"Session completed: {session.session_id}")

        except DefNotFoundError:
            self.logger.warning(f"Agent {self.agent_def.id} no longer exists")
        except Exception as e:
            self.logger.error(f"Session failed: {e}")
            self.job.message = "."
            await self.agent_queue.put(self.job)
```

## AgentDef Changes

### New Field

```python
class AgentDef(BaseModel):
    id: str
    name: str
    description: str = ""
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = True
    max_concurrency: int = Field(default=1, ge=1)  # NEW
```

### Example: agents/pickle/AGENT.md

```yaml
---
name: Pickle
description: General-purpose assistant
llm:
  temperature: 0.7
max_concurrency: 3
---

You are Pickle, a helpful AI assistant...
```

### Example: agents/cookie/AGENT.md

```yaml
---
name: Cookie
description: Memory and context assistant
llm:
  temperature: 0.5
# No max_concurrency = defaults to 1
---

You are Cookie, you manage long-term memory...
```

## Error Handling

| Case | Behavior |
|------|----------|
| Agent deleted | `DefNotFoundError` caught, job not requeued |
| Invalid max_concurrency | Pydantic validation error at load time |
| Semaphore memory leak | Threshold-based cleanup removes stale semaphores |
| Job crash | Requeue with "." message (preserved from current design) |

## Migration Path

### Files Changed

```
src/picklebot/
├── core/
│   ├── agent_def.py        # Add max_concurrency field
│   └── agent_loader.py     # Parse max_concurrency from frontmatter
└── server/
    └── agent_worker.py     # AgentJobRouter + SessionExecutor
```

### Migration Steps

1. Add `max_concurrency` to `AgentDef` with default=1 (backward compatible)
2. Update `AgentLoader` to parse `max_concurrency` from frontmatter
3. Refactor `agent_worker.py`:
   - Rename `AgentWorker` → `AgentJobRouter`
   - Add `SessionExecutor` class
   - Add semaphore management
4. Update `server.py` import
5. Update `agents/pickle/AGENT.md` with `max_concurrency: 3` (optional)

### Tests to Update

- `tests/server/test_agent_worker.py` - Update for new architecture
- `tests/core/test_agent_def.py` - Add tests for `max_concurrency` field
- `tests/core/test_agent_loader.py` - Add tests for parsing `max_concurrency`

## Benefits Summary

| Goal | How Achieved |
|------|--------------|
| **Performance** | Multiple sessions per agent run concurrently |
| **Isolation** | Per-agent semaphores, agent A doesn't block agent B |
| **Flexibility** | `max_concurrency` per agent, scale independently |
| **Simplicity** | Single queue, no multi-queue management |
| **Hot reload** | No caching = config changes picked up immediately |
| **Ordering** | Semaphore ensures FIFO per agent |
