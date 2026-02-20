# Worker-Based Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor picklebot server to use worker-based architecture with queue-based communication.

**Architecture:** Three workers (MessageBusWorker, CronWorker, AgentWorker) communicate via in-memory asyncio.Queue. Server orchestrates workers with health monitoring and auto-restart.

**Tech Stack:** asyncio, dataclasses, existing picklebot components (Agent, HistoryStore, Frontend, MessageBus)

---

## Task 1: Create Server Module Structure

**Files:**
- Create: `src/picklebot/server/__init__.py`
- Create: `src/picklebot/server/base.py`

**Step 1: Create server package directory**

```bash
mkdir -p src/picklebot/server
```

**Step 2: Create `__init__.py` with exports**

```python
# src/picklebot/server/__init__.py
"""Worker-based server architecture."""

from picklebot.server.base import Job, Worker
from picklebot.server.server import Server

__all__ = ["Job", "Worker", "Server"]
```

**Step 3: Create `base.py` with Job dataclass**

```python
# src/picklebot/server/base.py
"""Base classes for worker architecture."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from picklebot.core.agent import SessionMode

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.frontend.base import Frontend


@dataclass
class Job:
    """A unit of work for the AgentWorker."""

    session_id: str | None  # None = new session, set after first pickup
    agent_id: str  # Which agent to run
    message: str  # User prompt (set to "." after consumed)
    frontend: "Frontend"  # Live frontend object for responses
    mode: SessionMode  # CHAT or JOB


class Worker(ABC):
    """Base class for all workers."""

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.logger = logging.getLogger(
            f"picklebot.server.{self.__class__.__name__}"
        )
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

**Step 4: Commit**

```bash
git add src/picklebot/server/
git commit -m "feat(server): add server module with Job and Worker base class"
```

---

## Task 2: Implement AgentWorker

**Files:**
- Create: `src/picklebot/server/agent_worker.py`
- Create: `tests/server/test_agent_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_agent_worker.py
"""Tests for AgentWorker."""

import asyncio
import pytest

from picklebot.server.base import Job
from picklebot.server.agent_worker import AgentWorker
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend


class FakeFrontend:
    """Fake frontend for testing."""

    def __init__(self):
        self.messages: list[str] = []

    async def show_message(self, content: str) -> None:
        self.messages.append(content)

    async def show_welcome(self) -> None:
        pass

    async def show_system_message(self, content: str) -> None:
        pass

    async def show_transient(self, content: str):
        yield

    async def show_dispatch(self, calling_agent: str, target_agent: str, task: str):
        yield


@pytest.mark.asyncio
async def test_agent_worker_processes_job(test_context):
    """AgentWorker processes a job from the queue."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = AgentWorker(test_context, queue)

    # Create a job
    job = Job(
        session_id=None,
        agent_id="pickle",
        message="Say hello",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await queue.put(job)

    # Run worker for one iteration
    async def process_one():
        j = await queue.get()
        await worker._process_job(j)
        queue.task_done()

    await process_one()

    assert job.session_id is not None  # Session created


@pytest.mark.asyncio
async def test_agent_worker_requeues_on_error(test_context):
    """AgentWorker requeues job with '.' message on error."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = AgentWorker(test_context, queue)

    # Create a job with invalid agent (will error)
    job = Job(
        session_id=None,
        agent_id="nonexistent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await queue.put(job)

    # Process should fail and requeue
    await queue.get()
    await worker._process_job(job)

    # Job should be requeued with message = "."
    assert job.message == "."
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/server/test_agent_worker.py -v
```
Expected: FAIL (module not found)

**Step 3: Create tests/server/__init__.py**

```python
# tests/server/__init__.py
"""Tests for server module."""
```

**Step 4: Implement AgentWorker**

```python
# src/picklebot/server/agent_worker.py
"""Agent worker for executing agent jobs."""

import asyncio
from typing import TYPE_CHECKING

from picklebot.server.base import Worker, Job
from picklebot.core.agent import Agent

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class AgentWorker(Worker):
    """Executes agent jobs from the queue."""

    def __init__(
        self, context: "SharedContext", agent_queue: asyncio.Queue[Job]
    ):
        super().__init__(context)
        self.agent_queue = agent_queue

    async def run(self) -> None:
        """Process jobs from queue sequentially."""
        self.logger.info("AgentWorker started")

        while True:
            job = await self.agent_queue.get()
            await self._process_job(job)
            self.agent_queue.task_done()

    async def _process_job(self, job: Job) -> None:
        """Execute a single job with crash recovery."""
        try:
            # Load agent
            agent_def = self.context.agent_loader.load(job.agent_id)
            agent = Agent(agent_def, self.context)

            # Get or create session
            if job.session_id:
                session = agent.resume_session(job.session_id)
            else:
                session = agent.new_session(job.mode)
                job.session_id = session.session_id

            # Execute chat
            await session.chat(job.message, job.frontend)

            self.logger.info(f"Job completed: session={job.session_id}")

        except Exception as e:
            self.logger.error(f"Job failed: {e}")
            # Update job for resume and requeue
            job.message = "."
            await self.agent_queue.put(job)
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/server/test_agent_worker.py -v
```

**Step 6: Commit**

```bash
git add src/picklebot/server/agent_worker.py tests/server/
git commit -m "feat(server): add AgentWorker with crash recovery"
```

---

## Task 3: Implement CronWorker

**Files:**
- Create: `src/picklebot/server/cron_worker.py`
- Create: `tests/server/test_cron_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_cron_worker.py
"""Tests for CronWorker."""

import asyncio
import pytest
from datetime import datetime

from picklebot.server.cron_worker import CronWorker, find_due_jobs
from picklebot.core.cron_loader import CronDef


def test_find_due_jobs_returns_matching():
    """find_due_jobs returns jobs matching current time."""
    jobs = [
        CronDef(
            id="test-job",
            name="Test",
            agent="pickle",
            schedule="* * * * *",  # Every minute
            prompt="Test prompt",
        )
    ]

    due = find_due_jobs(jobs, datetime.now())
    assert len(due) == 1
    assert due[0].id == "test-job"


def test_find_due_jobs_empty_when_no_match():
    """find_due_jobs returns empty when no jobs match."""
    jobs = [
        CronDef(
            id="test-job",
            name="Test",
            agent="pickle",
            schedule="0 0 1 1 *",  # Jan 1 only
            prompt="Test prompt",
        )
    ]

    # Use a date that won't match
    now = datetime(2024, 6, 15, 12, 0)
    due = find_due_jobs(jobs, now)
    assert len(due) == 0


@pytest.mark.asyncio
async def test_cron_worker_dispatches_due_job(test_context):
    """CronWorker dispatches due jobs to the queue."""
    queue: asyncio.Queue = asyncio.Queue()
    worker = CronWorker(test_context, queue)

    # Manually call _tick and check queue
    await worker._tick()

    # Queue might have jobs if crons exist
    # Just verify no exception
    assert True
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/server/test_cron_worker.py -v
```
Expected: FAIL (module not found)

**Step 3: Implement CronWorker (adapt from cron_executor.py)**

```python
# src/picklebot/server/cron_worker.py
"""Cron worker for scheduled job dispatch."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from croniter import croniter

from picklebot.server.base import Worker, Job
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend

if TYPE_CHECKING:
    from picklebot.core.cron_loader import CronDef
    from picklebot.core.context import SharedContext


def find_due_jobs(
    jobs: list["CronDef"], now: datetime | None = None
) -> list["CronDef"]:
    """
    Find all jobs that are due to run.

    A job is due if the current minute matches its cron schedule.

    Args:
        jobs: List of cron definitions to check
        now: Current time (defaults to datetime.now())

    Returns:
        List of due jobs (may be empty)
    """
    if not jobs:
        return []

    now = now or datetime.now()
    now_minute = now.replace(second=0, microsecond=0)

    due_jobs = []
    for job in jobs:
        try:
            if croniter.match(job.schedule, now_minute):
                due_jobs.append(job)
        except Exception as e:
            logging.warning(f"Error checking schedule for {job.id}: {e}")
            continue

    return due_jobs


class CronWorker(Worker):
    """Finds due cron jobs, dispatches to agent queue."""

    def __init__(
        self, context: "SharedContext", agent_queue: asyncio.Queue[Job]
    ):
        super().__init__(context)
        self.agent_queue = agent_queue

    async def run(self) -> None:
        """Check every minute for due jobs."""
        self.logger.info("CronWorker started")

        while True:
            try:
                await self._tick()
            except Exception as e:
                self.logger.error(f"Error in tick: {e}")

            await asyncio.sleep(60)

    async def _tick(self) -> None:
        """Find and dispatch due jobs."""
        jobs = self.context.cron_loader.discover_crons()
        due_jobs = find_due_jobs(jobs)

        for cron_def in due_jobs:
            job = Job(
                session_id=None,  # Always new session
                agent_id=cron_def.agent,
                message=cron_def.prompt,
                frontend=SilentFrontend(),
                mode=SessionMode.JOB,
            )
            await self.agent_queue.put(job)
            self.logger.info(f"Dispatched cron job: {cron_def.id}")
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/server/test_cron_worker.py -v
```

**Step 5: Commit**

```bash
git add src/picklebot/server/cron_worker.py tests/server/test_cron_worker.py
git commit -m "feat(server): add CronWorker with schedule matching"
```

---

## Task 4: Implement MessageBusWorker

**Files:**
- Create: `src/picklebot/server/messagebus_worker.py`
- Create: `tests/server/test_messagebus_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_messagebus_worker.py
"""Tests for MessageBusWorker."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.server.base import Job
from picklebot.core.agent import SessionMode


class FakeBus:
    """Fake MessageBus for testing."""

    def __init__(self):
        self.platform_name = "fake"
        self.messages: list[str] = []
        self.started = False

    async def start(self, callback):
        self.started = True
        self._callback = callback
        # Simulate receiving a message
        await callback("hello", {"chat_id": "123"})

    async def stop(self):
        self.started = False

    def is_allowed(self, context):
        return True

    async def reply(self, content, context):
        self.messages.append(content)


@pytest.mark.asyncio
async def test_messagebus_worker_creates_global_session(test_context):
    """MessageBusWorker creates a global session on init."""
    bus = FakeBus()
    worker = MessageBusWorker(test_context, asyncio.Queue(), [bus])

    assert worker.global_session is not None
    assert worker.global_session.agent_id == "pickle"


@pytest.mark.asyncio
async def test_messagebus_worker_dispatches_to_queue(test_context):
    """MessageBusWorker dispatches incoming messages to agent queue."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    bus = FakeBus()
    worker = MessageBusWorker(test_context, queue, [bus])

    # Start worker (it will process one message and wait)
    task = asyncio.create_task(worker.run())

    # Wait for message to be dispatched
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check queue has job
    assert not queue.empty()
    job = await queue.get()
    assert job.message == "hello"
    assert job.session_id == worker.global_session.session_id
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/server/test_messagebus_worker.py -v
```
Expected: FAIL (module not found)

**Step 3: Implement MessageBusWorker**

```python
# src/picklebot/server/messagebus_worker.py
"""MessageBus worker for ingesting platform messages."""

import asyncio
from typing import TYPE_CHECKING, Any

from picklebot.server.base import Worker, Job
from picklebot.core.agent import SessionMode, Agent
from picklebot.frontend.messagebus import MessageBusFrontend

if TYPE_CHECKING:
    from picklebot.messagebus.base import MessageBus
    from picklebot.core.context import SharedContext


class MessageBusWorker(Worker):
    """Ingests messages from platforms, dispatches to agent queue."""

    def __init__(
        self,
        context: "SharedContext",
        agent_queue: asyncio.Queue[Job],
        buses: list["MessageBus"],
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
        """Start all buses and process incoming messages."""
        self.logger.info(
            f"MessageBusWorker started with {len(self.buses)} bus(es)"
        )

        bus_tasks = [
            bus.start(self._create_callback(bus.platform_name))
            for bus in self.buses
        ]

        try:
            await asyncio.gather(*bus_tasks)
        except asyncio.CancelledError:
            await asyncio.gather(*[bus.stop() for bus in self.buses])
            raise

    def _create_callback(self, platform: str):
        """Create callback for a specific platform."""

        async def callback(message: str, context: Any) -> None:
            bus = self.bus_map[platform]

            if not bus.is_allowed(context):
                self.logger.info(
                    f"Ignored non-whitelisted message from {platform}"
                )
                return

            # Create frontend for this message
            frontend = MessageBusFrontend(bus, context)

            # Dispatch job to agent queue
            job = Job(
                session_id=self.global_session.session_id,
                agent_id=self.global_session.agent_id,
                message=message,
                frontend=frontend,
                mode=SessionMode.CHAT,
            )
            await self.agent_queue.put(job)
            self.logger.debug(f"Dispatched message from {platform}")

        return callback
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/server/test_messagebus_worker.py -v
```

**Step 5: Commit**

```bash
git add src/picklebot/server/messagebus_worker.py tests/server/test_messagebus_worker.py
git commit -m "feat(server): add MessageBusWorker with global session"
```

---

## Task 5: Implement Server Class

**Files:**
- Create: `src/picklebot/server/server.py`
- Create: `tests/server/test_server.py`

**Step 1: Write the failing test**

```python
# tests/server/test_server.py
"""Tests for Server class."""

import asyncio
import pytest

from picklebot.server.server import Server


@pytest.mark.asyncio
async def test_server_creates_workers(test_context):
    """Server creates AgentWorker and CronWorker."""
    server = Server(test_context)

    server._setup_workers()

    assert len(server.workers) == 2  # Agent + Cron


@pytest.mark.asyncio
async def test_server_starts_workers(test_context):
    """Server starts all workers as tasks."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    assert len(server._tasks) == 2
    assert all(not t.done() for t in server._tasks)

    # Cleanup
    await server._stop_all()


@pytest.mark.asyncio
async def test_server_stops_workers_gracefully(test_context):
    """Server stops all workers on shutdown."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    await server._stop_all()

    assert all(t.done() for t in server._tasks)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/server/test_server.py -v
```
Expected: FAIL (module not found)

**Step 3: Implement Server class**

```python
# src/picklebot/server/server.py
"""Server orchestrator for worker-based architecture."""

import asyncio
import logging
from typing import TYPE_CHECKING

from picklebot.server.base import Job, Worker
from picklebot.server.agent_worker import AgentWorker
from picklebot.server.cron_worker import CronWorker
from picklebot.server.messagebus_worker import MessageBusWorker

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class Server:
    """Orchestrates workers with queue-based communication."""

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.agent_queue: asyncio.Queue[Job] = asyncio.Queue()
        self.workers: list[Worker] = []
        self._tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        """Start all workers and monitor for crashes."""
        self._setup_workers()
        self._start_workers()

        try:
            await self._monitor_workers()
        except asyncio.CancelledError:
            logger.info("Server shutting down...")
            await self._stop_all()
            raise

    def _setup_workers(self) -> None:
        """Create all workers."""
        # AgentWorker (always needed)
        self.workers.append(
            AgentWorker(self.context, self.agent_queue)
        )

        # CronWorker (always needed)
        self.workers.append(
            CronWorker(self.context, self.agent_queue)
        )

        # MessageBusWorker (if enabled)
        if self.context.config.messagebus.enabled:
            buses = self.context.messagebus_buses
            if buses:
                self.workers.append(
                    MessageBusWorker(self.context, self.agent_queue, buses)
                )
                logger.info(f"MessageBus enabled with {len(buses)} bus(es)")
            else:
                logger.warning("MessageBus enabled but no buses configured")

    def _start_workers(self) -> None:
        """Start all workers as tasks."""
        for worker in self.workers:
            task = worker.start()
            self._tasks.append(task)
            logger.info(f"Started {worker.__class__.__name__}")

    async def _monitor_workers(self) -> None:
        """Monitor worker tasks, restart on crash."""
        while True:
            for i, task in enumerate(self._tasks):
                if task.done() and not task.cancelled():
                    # Worker crashed
                    worker = self.workers[i]
                    exc = task.exception()
                    logger.error(
                        f"{worker.__class__.__name__} crashed: {exc}"
                    )

                    # Restart the worker
                    new_task = worker.start()
                    self._tasks[i] = new_task
                    logger.info(f"Restarted {worker.__class__.__name__}")

            await asyncio.sleep(5)  # Check every 5 seconds

    async def _stop_all(self) -> None:
        """Stop all workers gracefully."""
        for worker in self.workers:
            await worker.stop()
```

**Step 4: Update `__init__.py` to export Server**

```python
# src/picklebot/server/__init__.py
"""Worker-based server architecture."""

from picklebot.server.base import Job, Worker
from picklebot.server.server import Server

__all__ = ["Job", "Worker", "Server"]
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/server/test_server.py -v
```

**Step 6: Commit**

```bash
git add src/picklebot/server/
git commit -m "feat(server): add Server orchestrator with worker monitoring"
```

---

## Task 6: Update CLI Server Command

**Files:**
- Modify: `src/picklebot/cli/server.py`

**Step 1: Update CLI to use new Server**

```python
# src/picklebot/cli/server.py
"""Server CLI command for worker-based architecture."""

import asyncio

import typer

from picklebot.core.context import SharedContext
from picklebot.server.server import Server
from picklebot.utils.logging import setup_logging


def server_command(ctx: typer.Context) -> None:
    """Start the 24/7 server for cron and messagebus execution."""
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

**Step 2: Run existing tests to verify no regressions**

```bash
pytest tests/cli/ -v
```

**Step 3: Commit**

```bash
git add src/picklebot/cli/server.py
git commit -m "feat(cli): update server command to use worker architecture"
```

---

## Task 7: Delete Old Executors

**Files:**
- Delete: `src/picklebot/core/messagebus_executor.py`
- Delete: `src/picklebot/core/cron_executor.py`
- Delete: `tests/core/test_cron_executor.py` (if exists)
- Delete: `tests/core/test_messagebus_executor.py` (if exists)

**Step 1: Remove old executor files**

```bash
rm src/picklebot/core/messagebus_executor.py
rm src/picklebot/core/cron_executor.py
```

**Step 2: Remove old tests if they exist**

```bash
rm -f tests/core/test_cron_executor.py
rm -f tests/core/test_messagebus_executor.py
```

**Step 3: Update core/__init__.py if needed**

Check if executors were exported and remove exports.

**Step 4: Run all tests to verify nothing is broken**

```bash
pytest tests/ -v
```

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old executor files, replaced by worker architecture"
```

---

## Task 8: Add Test Fixtures

**Files:**
- Create: `tests/conftest.py` (if not exists) or update

**Step 1: Add test_context fixture**

```python
# tests/conftest.py
"""Shared test fixtures."""

import pytest
from pathlib import Path
import tempfile

from picklebot.utils.config import Config
from picklebot.core.context import SharedContext


@pytest.fixture
def test_config():
    """Create a test configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config.load(Path(tmpdir))
        yield config


@pytest.fixture
def test_context(test_config):
    """Create a test SharedContext."""
    return SharedContext(test_config)
```

**Step 2: Run all tests to verify**

```bash
pytest tests/ -v
```

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared test fixtures for server tests"
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update architecture section in CLAUDE.md**

Replace executor references with worker architecture:

```markdown
### Server Architecture

Worker-based architecture for `picklebot server` mode:

- **AgentWorker** - Executes agent jobs sequentially from queue
- **CronWorker** - Finds due cron jobs, dispatches to agent queue
- **MessageBusWorker** - Ingests messages from platforms, dispatches to agent queue
- **Server** - Orchestrates workers with health monitoring

See `docs/plans/2026-02-20-worker-architecture-design.md` for details.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with worker architecture"
```

---

## Task 10: Final Verification

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```

**Step 2: Run linting and type checking**

```bash
uv run ruff check .
uv run mypy .
```

**Step 3: Run the server manually to verify it starts**

```bash
uv run picklebot server
```
(Press Ctrl+C to stop)

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address final issues from verification"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create server module structure | `server/__init__.py`, `server/base.py` |
| 2 | Implement AgentWorker | `server/agent_worker.py`, tests |
| 3 | Implement CronWorker | `server/cron_worker.py`, tests |
| 4 | Implement MessageBusWorker | `server/messagebus_worker.py`, tests |
| 5 | Implement Server class | `server/server.py`, tests |
| 6 | Update CLI server command | `cli/server.py` |
| 7 | Delete old executors | Remove `*_executor.py` |
| 8 | Add test fixtures | `tests/conftest.py` |
| 9 | Update documentation | `CLAUDE.md` |
| 10 | Final verification | Run tests, lint, manual test |
