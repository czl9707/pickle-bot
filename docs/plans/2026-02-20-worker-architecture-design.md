# Worker-Based Architecture Design

## Overview

Refactor `picklebot server` mode to use a worker-based architecture with queue-based communication. This improves scalability and maintainability by separating concerns: message ingestion, job scheduling, and agent execution.

## Goals

- **Scalability** - Clear separation enables future horizontal scaling
- **Maintainability** - Workers in dedicated module, single responsibility
- **Resilience** - Auto-restart crashed workers with job recovery
- **No external dependencies** - In-memory queues, no Redis/RabbitMQ

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Server                               │
│  ┌─────────────┐    ┌─────────────┐                         │
│  │  AgentQueue │◄───│  Worker     │                         │
│  │ (asyncio    │    │  Registry   │                         │
│  │   Queue)    │    │             │                         │
│  └──────┬──────┘    └─────────────┘                         │
│         │                                                    │
│         │ enqueue Job                                        │
│         │                                                    │
│  ┌──────┴──────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ MessageBus  │    │    Cron     │    │    Agent    │     │
│  │   Worker    │───►│   Worker    │───►│   Worker    │     │
│  │             │    │             │    │             │     │
│  │ Telegram ──►│    │ Find due ──►│    │ Execute ──►│     │
│  │ Discord ──► │    │ jobs        │    │ agent chat  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                │             │
│                                                ▼             │
│                                          Frontend.reply()    │
└─────────────────────────────────────────────────────────────┘
```

**Flow:**
1. **MessageBusWorker** receives from Telegram/Discord → dispatches `Job` to queue
2. **CronWorker** checks schedules every 60s → dispatches `Job` to queue
3. **AgentWorker** picks up jobs → executes agent chat → frontend handles response

## Job Structure

```python
@dataclass
class Job:
    """A unit of work for the AgentWorker."""

    session_id: str | None    # None = new session, set after first pickup
    agent_id: str             # Which agent to run
    message: str              # User prompt (set to "." after consumed)
    frontend: Frontend        # Live frontend object for responses
    mode: SessionMode         # CHAT or JOB
```

### Job Lifecycle

| Stage | session_id | message |
|-------|------------|---------|
| Created by MessageBusWorker | `global_session_id` | `"hello"` |
| Created by CronWorker | `None` | cron prompt |
| First pickup (new session) | `None` → `"abc123"` | unchanged |
| After message consumed | `"abc123"` | `"."` |
| On crash + requeue | `"abc123"` | `"."` |

### Crash Recovery

When AgentWorker crashes mid-job:
1. Job is requeued with updated `session_id` and `message = "."`
2. Worker restarts, picks up job
3. Resumes session from HistoryStore (file-based persistence)
4. LLM sees history + "." message, naturally continues

This leverages existing HistoryStore as the checkpoint mechanism.

## Workers

### Worker Base Class

```python
class Worker(ABC):
    """Base class for all workers."""

    def __init__(self, context: SharedContext):
        self.context = context
        self.logger = logging.getLogger(f"picklebot.server.{self.__class__.__name__}")
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def run(self) -> None:
        """Main worker loop. Runs until cancelled."""
        pass

    def start(self) -> asyncio.Task:
        """Start the worker as an asyncio Task."""
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
```

### AgentWorker

Executes agent jobs from the queue sequentially.

```python
class AgentWorker(Worker):
    def __init__(self, context: SharedContext, agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue

    async def run(self) -> None:
        while True:
            job = await self.agent_queue.get()
            await self._process_job(job)
            self.agent_queue.task_done()

    async def _process_job(self, job: Job) -> None:
        try:
            agent_def = self.context.agent_loader.load(job.agent_id)
            agent = Agent(agent_def, self.context)

            if job.session_id:
                session = agent.resume_session(job.session_id)
            else:
                session = agent.new_session(job.mode)
                job.session_id = session.session_id

            await session.chat(job.message, job.frontend)

        except Exception as e:
            self.logger.error(f"Job failed: {e}")
            job.message = "."
            await self.agent_queue.put(job)
```

### MessageBusWorker

Ingests messages from platforms, dispatches to agent queue. Owns a global session.

```python
class MessageBusWorker(Worker):
    def __init__(
        self,
        context: SharedContext,
        agent_queue: asyncio.Queue[Job],
        buses: list[MessageBus],
    ):
        super().__init__(context)
        self.agent_queue = agent_queue
        self.buses = buses
        self.bus_map = {bus.platform_name: bus for bus in buses}

        # Create global session on startup
        agent_def = context.agent_loader.load(context.config.default_agent)
        agent = Agent(agent_def, context)
        self.global_session = agent.new_session(SessionMode.CHAT)

    async def run(self) -> None:
        bus_tasks = [
            bus.start(self._create_callback(bus.platform_name))
            for bus in self.buses
        ]
        await asyncio.gather(*bus_tasks)

    def _create_callback(self, platform: str):
        async def callback(message: str, context: Any) -> None:
            bus = self.bus_map[platform]
            if not bus.is_allowed(context):
                return

            frontend = MessageBusFrontend(bus, context)
            job = Job(
                session_id=self.global_session.session_id,
                agent_id=self.global_session.agent_id,
                message=message,
                frontend=frontend,
                mode=SessionMode.CHAT,
            )
            await self.agent_queue.put(job)

        return callback
```

### CronWorker

Finds due cron jobs, dispatches to agent queue. Always creates new sessions.

```python
class CronWorker(Worker):
    def __init__(self, context: SharedContext, agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue

    async def run(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception as e:
                self.logger.error(f"Error in tick: {e}")
            await asyncio.sleep(60)

    async def _tick(self) -> None:
        jobs = self.context.cron_loader.discover_crons()
        due_jobs = find_due_jobs(jobs)  # Reuse existing helper

        for cron_def in due_jobs:
            job = Job(
                session_id=None,
                agent_id=cron_def.agent,
                message=cron_def.prompt,
                frontend=SilentFrontend(),
                mode=SessionMode.JOB,
            )
            await self.agent_queue.put(job)
```

## Server Class

Orchestrates workers with health monitoring and auto-restart.

```python
class Server:
    def __init__(self, context: SharedContext):
        self.context = context
        self.agent_queue: asyncio.Queue[Job] = asyncio.Queue()
        self.workers: list[Worker] = []
        self._tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        self._setup_workers()
        self._start_workers()

        try:
            await self._monitor_workers()
        except asyncio.CancelledError:
            await self._stop_all()
            raise

    def _setup_workers(self) -> None:
        self.workers.append(AgentWorker(self.context, self.agent_queue))
        self.workers.append(CronWorker(self.context, self.agent_queue))

        if self.context.config.messagebus.enabled:
            buses = self.context.messagebus_buses
            if buses:
                self.workers.append(
                    MessageBusWorker(self.context, self.agent_queue, buses)
                )

    def _start_workers(self) -> None:
        for worker in self.workers:
            self._tasks.append(worker.start())

    async def _monitor_workers(self) -> None:
        while True:
            for i, task in enumerate(self._tasks):
                if task.done() and not task.cancelled():
                    worker = self.workers[i]
                    self._tasks[i] = worker.start()  # Restart
            await asyncio.sleep(5)

    async def _stop_all(self) -> None:
        for worker in self.workers:
            await worker.stop()
```

## File Structure

```
src/picklebot/server/
├── __init__.py           # exports Server, Job
├── base.py               # Job dataclass, Worker base class
├── server.py             # Server class
├── agent_worker.py       # AgentWorker
├── messagebus_worker.py  # MessageBusWorker
└── cron_worker.py        # CronWorker
```

### Files to Delete

- `src/picklebot/core/messagebus_executor.py`
- `src/picklebot/core/cron_executor.py`

### Files to Modify

- `src/picklebot/cli/server.py` - simplified to use `Server` class

## CLI Changes

```python
# cli/server.py (simplified)
def server_command(ctx: typer.Context) -> None:
    config = ctx.obj.get("config")
    setup_logging(config, console_output=True)

    typer.echo("Starting pickle-bot server...")
    typer.echo("Press Ctrl+C to stop")

    try:
        context = SharedContext(config)
        asyncio.run(Server(context).run())
    except KeyboardInterrupt:
        typer.echo("\nServer stopped")
```

## Migration Path

1. Create `server/` module with all workers
2. Copy/adapt code from executors (reuse `find_due_jobs`)
3. Update `cli/server.py` to use new `Server`
4. Update imports in `__init__.py` files
5. Delete old executor files
6. Update tests

## Configuration

No changes needed - uses existing config structure.

## Future Considerations

- Multiple AgentWorkers for parallel processing (add `agent_workers` config)
- Per-chat sessions (MessageBusWorker creates session per chat_id)
- External queue backend (Redis/RabbitMQ) for multi-process deployment
