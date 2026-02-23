# Subagent Concurrency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route subagent dispatches through the worker job queue to respect per-agent concurrency limits.

**Architecture:** Add `result_future` and `retry_count` to Job model. Workers access queue via SharedContext's lazy `agent_queue` property. SessionExecutor sets result/exception on future. Subagent tool dispatches through queue and awaits future.

**Tech Stack:** asyncio, dataclasses, pytest

---

## Task 1: Add result_future and retry_count to Job

**Files:**
- Modify: `src/picklebot/server/base.py`
- Test: `tests/server/test_base.py`

**Step 1: Write the failing test**

```python
# tests/server/test_base.py
import asyncio
from picklebot.server.base import Job
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend


def test_job_has_result_future():
    """Job should have a result_future field."""
    job = Job(
        agent_id="test",
        message="hello",
        frontend=SilentFrontend(),
    )
    assert hasattr(job, "result_future")
    assert isinstance(job.result_future, asyncio.Future)


def test_job_has_retry_count():
    """Job should have a retry_count field defaulting to 0."""
    job = Job(
        agent_id="test",
        message="hello",
        frontend=SilentFrontend(),
    )
    assert hasattr(job, "retry_count")
    assert job.retry_count == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_base.py -v`
Expected: FAIL with "AttributeError" or similar

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/base.py
# Add to imports at top:
import asyncio
from dataclasses import dataclass, field

# Update Job dataclass:
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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/base.py tests/server/test_base.py
git commit -m "feat(server): add result_future and retry_count to Job"
```

---

## Task 2: Add lazy agent_queue property to SharedContext

**Files:**
- Modify: `src/picklebot/core/context.py`
- Test: `tests/core/test_context.py`

**Step 1: Write the failing test**

```python
# tests/core/test_context.py
import asyncio
import pytest
from picklebot.core.context import SharedContext


def test_shared_context_has_agent_queue():
    """SharedContext should have an agent_queue property."""
    ctx = SharedContext(
        config=mock_config(),
        frontend=mock_frontend(),
        tool_registry=mock_tool_registry(),
        agent_loader=mock_agent_loader(),
        skill_loader=mock_skill_loader(),
        cron_loader=mock_cron_loader(),
    )
    assert hasattr(ctx, "agent_queue")


def test_agent_queue_is_lazy():
    """agent_queue should be created lazily on first access."""
    ctx = SharedContext(
        config=mock_config(),
        frontend=mock_frontend(),
        tool_registry=mock_tool_registry(),
        agent_loader=mock_agent_loader(),
        skill_loader=mock_skill_loader(),
        cron_loader=mock_cron_loader(),
    )
    # Before access, internal storage should be None
    assert ctx._agent_queue is None

    # After access, should be a Queue
    queue = ctx.agent_queue
    assert isinstance(queue, asyncio.Queue)

    # Same queue on subsequent access
    assert ctx.agent_queue is queue


# Helper mocks - add at top of file or in conftest
def mock_config():
    from unittest.mock import MagicMock
    config = MagicMock()
    config.agents_path = MagicMock()
    config.skills_path = MagicMock()
    config.crons_path = MagicMock()
    return config


def mock_frontend():
    from unittest.mock import MagicMock
    return MagicMock()


def mock_tool_registry():
    from unittest.mock import MagicMock
    return MagicMock()


def mock_agent_loader():
    from unittest.mock import MagicMock
    return MagicMock()


def mock_skill_loader():
    from unittest.mock import MagicMock
    return MagicMock()


def mock_cron_loader():
    from unittest.mock import MagicMock
    return MagicMock()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_context.py -v`
Expected: FAIL with "AttributeError: 'SharedContext' object has no attribute 'agent_queue'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/core/context.py
# Add to imports:
from dataclasses import dataclass, field

# Update SharedContext:
@dataclass
class SharedContext:
    config: Config
    frontend: "Frontend"
    tool_registry: "ToolRegistry"
    agent_loader: "AgentLoader"
    skill_loader: "SkillLoader"
    cron_loader: "CronLoader"
    _agent_queue: asyncio.Queue["Job"] | None = field(default=None, init=False, repr=False)

    @property
    def agent_queue(self) -> asyncio.Queue["Job"]:
        """Lazily create agent queue on first access."""
        if self._agent_queue is None:
            self._agent_queue = asyncio.Queue()
        return self._agent_queue
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/context.py tests/core/test_context.py
git commit -m "feat(core): add lazy agent_queue property to SharedContext"
```

---

## Task 3: Update SessionExecutor with future and retry logic

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Test: `tests/server/test_agent_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_agent_worker.py
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from picklebot.server.base import Job
from picklebot.server.agent_worker import SessionExecutor, MAX_RETRIES
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.agent_loader.load.return_value = MagicMock(id="test-agent")
    return context


@pytest.fixture
def mock_agent_def():
    return MagicMock(id="test-agent", max_concurrency=1)


@pytest.fixture
def mock_semaphore():
    return asyncio.Semaphore(1)


@pytest.mark.asyncio
async def test_session_executor_sets_result_on_success(mock_context, mock_agent_def, mock_semaphore):
    """SessionExecutor should set result on future when session succeeds."""
    job = Job(
        agent_id="test-agent",
        message="hello",
        frontend=SilentFrontend(),
    )

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        mock_session = AsyncMock()
        mock_session.chat = AsyncMock(return_value="response text")
        mock_session.session_id = "session-123"

        mock_agent = MagicMock()
        mock_agent.new_session.return_value = mock_session
        MockAgent.return_value = mock_agent

        executor = SessionExecutor(mock_context, mock_agent_def, job, mock_semaphore)
        await executor.run()

    assert job.result_future.done()
    assert job.result_future.result() == "response text"


@pytest.mark.asyncio
async def test_session_executor_requeues_on_first_failure(mock_context, mock_agent_def, mock_semaphore):
    """SessionExecutor should requeue job with incremented retry_count on failure."""
    job = Job(
        agent_id="test-agent",
        message="hello",
        frontend=SilentFrontend(),
        retry_count=0,
    )

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("boom")

        executor = SessionExecutor(mock_context, mock_agent_def, job, mock_semaphore)
        await executor.run()

    # Job should be requeued
    requeued_job = mock_context.agent_queue.get_nowait()
    assert requeued_job.retry_count == 1
    assert requeued_job.message == "."


@pytest.mark.asyncio
async def test_session_executor_sets_exception_after_max_retries(mock_context, mock_agent_def, mock_semaphore):
    """SessionExecutor should set exception after MAX_RETRIES failures."""
    job = Job(
        agent_id="test-agent",
        message="hello",
        frontend=SilentFrontend(),
        retry_count=MAX_RETRIES,  # Already at max
    )

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("final boom")

        executor = SessionExecutor(mock_context, mock_agent_def, job, mock_semaphore)
        await executor.run()

    assert job.result_future.done()
    assert isinstance(job.result_future.exception(), Exception)
    assert str(job.result_future.exception()) == "final boom"

    # Should NOT be requeued
    assert mock_context.agent_queue.empty()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_agent_worker.py -v`
Expected: FAIL - tests expect new behavior

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/agent_worker.py
# Add constant at module level:
MAX_RETRIES = 3

# Update SessionExecutor.__init__ - remove agent_queue param:
def __init__(
    self,
    context: "SharedContext",
    agent_def: "AgentDef",
    job: Job,
    semaphore: asyncio.Semaphore,
):
    self.context = context
    self.agent_def = agent_def
    self.job = job
    self.semaphore = semaphore
    self.logger = logging.getLogger(
        f"picklebot.server.SessionExecutor.{agent_def.id}"
    )

# Update _execute method:
async def _execute(self) -> None:
    """Run the actual agent session."""
    try:
        agent = Agent(self.agent_def, self.context)

        if self.job.session_id:
            try:
                session = agent.resume_session(self.job.session_id)
            except ValueError:
                self.logger.warning(
                    f"Session {self.job.session_id} not found, creating new"
                )
                session = agent.new_session(
                    self.job.mode, session_id=self.job.session_id
                )
        else:
            session = agent.new_session(self.job.mode)
            self.job.session_id = session.session_id

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

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/agent_worker.py tests/server/test_agent_worker.py
git commit -m "feat(server): add result future and retry logic to SessionExecutor"
```

---

## Task 4: Update AgentDispatcherWorker to use context.agent_queue

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Test: `tests/server/test_agent_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_agent_worker.py - add to existing file
@pytest.mark.asyncio
async def test_agent_dispatcher_uses_context_queue():
    """AgentDispatcherWorker should get queue from context."""
    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.agent_loader.discover_agents.return_value = []

    dispatcher = AgentDispatcherWorker(context)

    # Should not have its own agent_queue attribute
    assert not hasattr(dispatcher, "agent_queue") or dispatcher.agent_queue is context.agent_queue
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_agent_worker.py::test_agent_dispatcher_uses_context_queue -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/agent_worker.py
# Update AgentDispatcherWorker.__init__:
def __init__(self, context: "SharedContext"):
    super().__init__(context)
    self._semaphores: dict[str, asyncio.Semaphore] = {}

# Update run method:
async def run(self) -> None:
    """Process jobs sequentially, dispatch to executors."""
    self.logger.info("AgentDispatcherWorker started")

    while True:
        job = await self.context.agent_queue.get()
        self._dispatch_job(job)
        self.context.agent_queue.task_done()
        self._maybe_cleanup_semaphores()

# Update _dispatch_job - pass context to SessionExecutor:
def _dispatch_job(self, job: Job) -> None:
    """Create executor task for job."""
    try:
        agent_def = self.context.agent_loader.load(job.agent_id)
    except DefNotFoundError as e:
        self.logger.error(f"Agent not found: {job.agent_id}: {e}")
        return

    sem = self._get_or_create_semaphore(agent_def)
    asyncio.create_task(
        SessionExecutor(self.context, agent_def, job, sem).run()
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/agent_worker.py tests/server/test_agent_worker.py
git commit -m "refactor(server): AgentDispatcherWorker uses context.agent_queue"
```

---

## Task 5: Update CronWorker to use context.agent_queue

**Files:**
- Modify: `src/picklebot/server/cron_worker.py`
- Test: `tests/server/test_cron_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_cron_worker.py - add or update
@pytest.mark.asyncio
async def test_cron_worker_uses_context_queue():
    """CronWorker should get queue from context."""
    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.cron_loader.discover_crons.return_value = []

    worker = CronWorker(context)

    # Should not have its own agent_queue attribute
    assert not hasattr(worker, "agent_queue") or worker.agent_queue is context.agent_queue
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_cron_worker.py -v`
Expected: FAIL (if test exists with old behavior)

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/cron_worker.py
# Update CronWorker.__init__:
def __init__(self, context: "SharedContext"):
    super().__init__(context)

# Update _tick method - use self.context.agent_queue:
async def _tick(self) -> None:
    """Find and dispatch due jobs."""
    jobs = self.context.cron_loader.discover_crons()
    due_jobs = find_due_jobs(jobs)

    for cron_def in due_jobs:
        job = Job(
            session_id=None,
            agent_id=cron_def.agent,
            message=cron_def.prompt,
            frontend=SilentFrontend(),
            mode=SessionMode.JOB,
        )
        await self.context.agent_queue.put(job)
        self.logger.info(f"Dispatched cron job: {cron_def.id}")

        if cron_def.one_off:
            cron_path = self.context.cron_loader.config.crons_path / cron_def.id
            shutil.rmtree(cron_path)
            self.logger.info(f"Deleted one-off cron job: {cron_def.id}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_cron_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/cron_worker.py tests/server/test_cron_worker.py
git commit -m "refactor(server): CronWorker uses context.agent_queue"
```

---

## Task 6: Update MessageBusWorker to use context.agent_queue

**Files:**
- Modify: `src/picklebot/server/messagebus_worker.py`
- Test: `tests/server/test_messagebus_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_messagebus_worker.py - add or update
@pytest.mark.asyncio
async def test_messagebus_worker_uses_context_queue():
    """MessageBusWorker should get queue from context."""
    from unittest.mock import MagicMock
    import asyncio

    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.config.messagebus.enabled = False
    context.messagebus_buses = []

    worker = MessageBusWorker.__new__(MessageBusWorker)
    worker.context = context

    # Should access queue via context
    assert worker.context.agent_queue is context.agent_queue
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_messagebus_worker.py -v`
Expected: FAIL (if test exists with old behavior)

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/messagebus_worker.py
# Update MessageBusWorker.__init__:
def __init__(self, context: "SharedContext"):
    super().__init__(context)
    self.buses = context.messagebus_buses
    self.bus_map = {bus.platform_name: bus for bus in self.buses}

    try:
        self.agent_def = context.agent_loader.load(context.config.default_agent)
        self.agent = Agent(self.agent_def, context)
    except DefNotFoundError as e:
        self.logger.error(
            f"Default agent not found: {context.config.default_agent}"
        )
        raise RuntimeError(f"Failed to initialize MessageBusWorker: {e}") from e

# Update callback in _create_callback:
async def callback(message: str, context: Any) -> None:
    try:
        bus = self.bus_map[platform]

        if not bus.is_allowed(context):
            self.logger.debug(
                f"Ignored non-whitelisted message from {platform}"
            )
            return

        user_id = context.user_id
        session_id = self._get_or_create_session_id(platform, user_id)
        frontend = MessageBusFrontend(bus, context)

        job = Job(
            session_id=session_id,
            agent_id=self.agent_def.id,
            message=message,
            frontend=frontend,
            mode=SessionMode.CHAT,
        )
        await self.context.agent_queue.put(job)  # Changed from self.agent_queue
        self.logger.debug(f"Dispatched message from {platform}")
    except Exception as e:
        self.logger.error(f"Error processing message from {platform}: {e}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_messagebus_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/messagebus_worker.py tests/server/test_messagebus_worker.py
git commit -m "refactor(server): MessageBusWorker uses context.agent_queue"
```

---

## Task 7: Update Server to remove queue creation

**Files:**
- Modify: `src/picklebot/server/server.py`
- Test: `tests/server/test_server.py`

**Step 1: Write the failing test**

```python
# tests/server/test_server.py - add or update
def test_server_uses_context_queue():
    """Server should not create its own queue, use context's."""
    from unittest.mock import MagicMock, patch
    import asyncio

    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.config.messagebus.enabled = False
    context.config.api.enabled = False

    with patch("picklebot.server.server.AgentDispatcherWorker"), \
         patch("picklebot.server.server.CronWorker"):
        server = Server(context)

        # Server should not have its own agent_queue
        assert not hasattr(server, "agent_queue")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_server.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/server.py
# Update Server.__init__:
def __init__(self, context: "SharedContext"):
    self.context = context
    self.workers: list[Worker] = []
    self._api_task: asyncio.Task | None = None

# Update _setup_workers:
def _setup_workers(self) -> None:
    """Create all workers."""
    self.workers.append(AgentDispatcherWorker(self.context))
    self.workers.append(CronWorker(self.context))

    if self.context.config.messagebus.enabled:
        buses = self.context.messagebus_buses
        if buses:
            self.workers.append(MessageBusWorker(self.context))
            logger.info(f"MessageBus enabled with {len(buses)} bus(es)")
        else:
            logger.warning("MessageBus enabled but no buses configured")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/server.py tests/server/test_server.py
git commit -m "refactor(server): remove queue creation, workers use context.agent_queue"
```

---

## Task 8: Update subagent_dispatch tool

**Files:**
- Modify: `src/picklebot/tools/subagent_tool.py`
- Test: `tests/tools/test_subagent_tool.py`

**Step 1: Write the failing test**

```python
# tests/tools/test_subagent_tool.py
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.server.base import Job


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.agent_loader.discover_agents.return_value = [
        MagicMock(id="target-agent", description="Target agent")
    ]
    context.agent_loader.load.return_value = MagicMock(
        id="target-agent",
        name="Target Agent"
    )
    return context


@pytest.fixture
def mock_frontend():
    frontend = MagicMock()
    frontend.show_dispatch = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
    return frontend


@pytest.mark.asyncio
async def test_subagent_dispatch_uses_queue(mock_context, mock_frontend):
    """subagent_dispatch should dispatch through queue when available."""
    tool = create_subagent_dispatch_tool("caller-agent", mock_context)
    assert tool is not None

    # Create a task that will resolve the future
    async def resolve_future():
        await asyncio.sleep(0.1)
        # Get the job from queue and resolve it
        job = await mock_context.agent_queue.get()
        job.session_id = "test-session"
        job.result_future.set_result("task completed")

    asyncio.create_task(resolve_future())

    result = await tool(mock_frontend, "target-agent", "do something")
    assert "task completed" in result
    assert "test-session" in result


@pytest.mark.asyncio
async def test_subagent_dispatch_fallback_when_no_queue(mock_context, mock_frontend):
    """subagent_dispatch should fall back to direct execution when no queue."""
    mock_context.agent_queue = None  # No queue (CLI mode)

    with patch("picklebot.tools.subagent_tool.Agent") as MockAgent:
        mock_session = AsyncMock()
        mock_session.chat = AsyncMock(return_value="direct response")
        mock_session.session_id = "direct-session"

        mock_agent = MagicMock()
        mock_agent.new_session.return_value = mock_session
        MockAgent.return_value = mock_agent

        tool = create_subagent_dispatch_tool("caller-agent", mock_context)
        result = await tool(mock_frontend, "target-agent", "do something")

    assert "direct response" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/picklebot/tools/subagent_tool.py
# Update the subagent_dispatch function:
@tool(
    name="subagent_dispatch",
    description=f"Dispatch a task to a specialized subagent.\n{agents_desc}",
    parameters={
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "enum": dispatchable_ids,
                "description": "ID of the agent to dispatch to",
            },
            "task": {
                "type": "string",
                "description": "The task for the subagent to perform",
            },
            "context": {
                "type": "string",
                "description": "Optional context information for the subagent",
            },
        },
        "required": ["agent_id", "task"],
    },
)
async def subagent_dispatch(
    frontend: "Frontend", agent_id: str, task: str, context: str = ""
) -> str:
    """Dispatch task to subagent, return result + session_id."""
    from picklebot.core.agent import Agent, SessionMode
    from picklebot.server.base import Job

    try:
        target_def = shared_context.agent_loader.load(agent_id)
    except DefNotFoundError:
        raise ValueError(f"Agent '{agent_id}' not found")

    user_message = task
    if context:
        user_message = f"{task}\n\nContext:\n{context}"

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
        # CLI fallback: direct execution
        subagent = Agent(target_def, shared_context)

        async with frontend.show_dispatch(current_agent_id, agent_id, task):
            session = subagent.new_session(SessionMode.JOB)
            response = await session.chat(user_message, SilentFrontend())

        result = {"result": response, "session_id": session.session_id}

    return json.dumps(result)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_subagent_tool.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/subagent_tool.py tests/tools/test_subagent_tool.py
git commit -m "feat(tools): subagent_dispatch uses queue with future for result"
```

---

## Task 9: Run full test suite and fix any issues

**Files:**
- Various test files as needed

**Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Fix any failing tests**

Update test assertions to match new behavior (constructor signatures, etc.)

**Step 3: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 4: Final commit**

```bash
git add .
git commit -m "test: update tests for subagent concurrency control"
```

---

## Task 10: Integration test

**Files:**
- Manual testing

**Step 1: Test server mode**

Start server and verify subagent dispatches queue properly:

```bash
uv run picklebot server
```

**Step 2: Test CLI mode**

Verify CLI still works with direct execution:

```bash
uv run picklebot chat
```

**Step 3: Final commit (if needed)**

```bash
git add .
git commit -m "fix: any integration issues"
```
