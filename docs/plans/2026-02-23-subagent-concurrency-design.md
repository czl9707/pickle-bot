# Subagent Dispatch Concurrency Control

**Date:** 2026-02-23
**Status:** Approved

## Problem

Workers use per-agent semaphores (`max_concurrency`) to limit concurrent sessions. However, subagent dispatches bypass this system entirely - they execute directly without respecting concurrency limits.

This creates two issues:

1. **Overload risk:** Subagent dispatches can exceed an agent's `max_concurrency` when worker jobs are already running
2. **Inconsistent tracking:** Subagent sessions don't flow through the unified job queue, making monitoring harder

## Goals

1. Subagent dispatches respect `max_concurrency` alongside worker jobs
2. All sessions flow through the same path for unified tracking

## Solution

Route subagent dispatches through the same job queue that workers use. Use `asyncio.Future` to return results from queued jobs back to the calling tool.

## Design

### 1. Job Model Changes

Add `result_future` and `retry_count` to Job:

```python
@dataclass
class Job:
    agent_id: str
    message: str
    frontend: "Frontend"
    mode: SessionMode = SessionMode.CHAT
    session_id: str | None = None
    result_future: asyncio.Future[str] = field(default_factory=asyncio.Future)
    retry_count: int = 0
```

**`result_future`**: Always created, used by subagent dispatches to await results. Worker jobs ignore it (garbage collected).

**`retry_count`**: Limits retry attempts on failure. After 3 failures, set exception instead of requeueing.

### 2. SharedContext with Lazy Queue

Add lazy `agent_queue` property to SharedContext:

```python
@dataclass
class SharedContext:
    config: Config
    frontend: "Frontend"
    tool_registry: "ToolRegistry"
    agent_loader: "AgentLoader"
    skill_loader: "SkillLoader"
    cron_loader: "CronLoader"
    _agent_queue: asyncio.Queue[Job] | None = field(default=None, init=False, repr=False)

    @property
    def agent_queue(self) -> asyncio.Queue[Job]:
        """Lazily create agent queue on first access."""
        if self._agent_queue is None:
            self._agent_queue = asyncio.Queue()
        return self._agent_queue
```

**Why lazy?** `asyncio.Queue()` requires a running event loop. SharedContext is created before `asyncio.run()`, so lazy initialization ensures the queue is created when first accessed (inside async context).

### 3. SessionExecutor Changes

Set result or exception on the future, with retry logic:

```python
MAX_RETRIES = 3

async def _execute(self) -> None:
    try:
        agent = Agent(self.agent_def, self.context)
        # ... session setup ...
        response = await session.chat(self.job.message, self.job.frontend)
        self.logger.info(f"Session completed: {session.session_id}")
        self.job.result_future.set_result(response)

    except Exception as e:
        self.logger.error(f"Session failed: {e}")

        if self.job.retry_count < MAX_RETRIES:
            self.job.retry_count += 1
            self.job.message = "."
            await self.context.agent_queue.put(self.job)
        else:
            self.job.result_future.set_exception(e)
```

**Flow:**
- Success → `set_result(response)` → done
- Failure + retries remaining → increment count, requeue
- Failure + max retries → `set_exception(e)` → caller receives exception

### 4. Worker Refactoring

Remove queue from worker constructors. Access via `context.agent_queue`:

**AgentDispatcherWorker:**
```python
class AgentDispatcherWorker(Worker):
    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def run(self) -> None:
        while True:
            job = await self.context.agent_queue.get()
            self._dispatch_job(job)
            self.context.agent_queue.task_done()
```

**CronWorker:**
```python
await self.context.agent_queue.put(job)
```

**MessageBusWorker:**
```python
await self.context.agent_queue.put(job)
```

### 5. Server Changes

Remove queue creation from Server. Workers get queue from context:

```python
class Server:
    def __init__(self, context: "SharedContext"):
        self.context = context
        self.workers: list[Worker] = []

    def _setup_workers(self) -> None:
        self.workers.append(AgentDispatcherWorker(self.context))
        self.workers.append(CronWorker(self.context))
        # ...
```

### 6. Subagent Tool Changes

Dispatch through queue when available, await future for result:

```python
async def subagent_dispatch(
    frontend: "Frontend", agent_id: str, task: str, context: str = ""
) -> str:
    from picklebot.core.agent import SessionMode
    from picklebot.server.base import Job

    target_def = shared_context.agent_loader.load(agent_id)
    user_message = f"{task}\n\nContext:\n{context}" if context else task

    if shared_context.agent_queue is not None:
        # Server mode: dispatch through queue
        job = Job(
            agent_id=agent_id,
            message=user_message,
            frontend=SilentFrontend(),
            mode=SessionMode.JOB,
        )

        async with frontend.show_dispatch(current_agent_id, agent_id, task):
            await shared_context.agent_queue.put(job)
            response = await job.result_future

        result = {"result": response, "session_id": job.session_id}
    else:
        # CLI fallback: direct execution (no concurrency control)
        subagent = Agent(target_def, shared_context)
        async with frontend.show_dispatch(current_agent_id, agent_id, task):
            session = subagent.new_session(SessionMode.JOB)
            response = await session.chat(user_message, SilentFrontend())
        result = {"result": response, "session_id": session.session_id}

    return json.dumps(result)
```

**CLI mode note:** Falls back to direct execution since there's typically no concurrency concern in single-session CLI usage.

## Summary of Changes

| Component | Change |
|-----------|--------|
| **Job** | Add `result_future` + `retry_count` |
| **SharedContext** | Add lazy `agent_queue` property |
| **SessionExecutor** | Set result/exception on future, retry logic (max 3) |
| **AgentDispatcherWorker** | Remove queue param, use `context.agent_queue` |
| **CronWorker** | Remove queue param, use `context.agent_queue` |
| **MessageBusWorker** | Remove queue param, use `context.agent_queue` |
| **Server** | Remove queue creation, workers get it from context |
| **subagent_tool** | Dispatch via queue when available, await future |

## Out of Scope

- **Deadlock detection:** If Agent A dispatches to B, and B dispatches to A, deadlock is possible. Not addressed in this design.
- **Timeout handling:** Callers can wrap `await future` in `asyncio.timeout()` if needed.
- **Priority queueing:** All jobs have equal priority.
