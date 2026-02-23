# Agent Concurrency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-agent concurrency control using semaphores, replacing AgentWorker with AgentJobRouter + SessionExecutor.

**Architecture:** Single shared queue with AgentJobRouter that creates per-agent semaphores. SessionExecutor runs each job as a task, waiting on its agent's semaphore before executing. This provides FIFO ordering per agent while allowing parallel execution across agents.

**Tech Stack:** asyncio.Semaphore, Pydantic validation, pytest-anyio

---

## Task 1: Add max_concurrency to AgentDef

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:18-26`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test**

```python
# tests/core/test_agent_loader.py

def test_agent_def_has_max_concurrency_with_default():
    """AgentDef has max_concurrency field with default value 1."""
    from picklebot.core.agent_loader import AgentDef
    from picklebot.utils.config import LLMConfig

    llm = LLMConfig(provider="test", model="test", api_key="test")
    agent_def = AgentDef(
        id="test",
        name="Test",
        system_prompt="Test prompt",
        llm=llm,
    )

    assert agent_def.max_concurrency == 1


def test_agent_def_max_concurrency_validation():
    """max_concurrency must be >= 1."""
    from picklebot.core.agent_loader import AgentDef
    from picklebot.utils.config import LLMConfig
    from pydantic import ValidationError

    llm = LLMConfig(provider="test", model="test", api_key="test")

    # Should fail with 0
    with pytest.raises(ValidationError):
        AgentDef(
            id="test",
            name="Test",
            system_prompt="Test prompt",
            llm=llm,
            max_concurrency=0,
        )

    # Should fail with negative
    with pytest.raises(ValidationError):
        AgentDef(
            id="test",
            name="Test",
            system_prompt="Test prompt",
            llm=llm,
            max_concurrency=-1,
        )
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::test_agent_def_has_max_concurrency_with_default -v`
Expected: FAIL with "AgentDef has no field 'max_concurrency'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/core/agent_loader.py
# Add to imports:
from pydantic import BaseModel, Field, ValidationError

# Modify AgentDef class:
class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    description: str = ""  # Brief description for dispatch tool
    system_prompt: str
    llm: LLMConfig
    allow_skills: bool = False
    max_concurrency: int = Field(default=1, ge=1)  # NEW
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::test_agent_def_has_max_concurrency_with_default tests/core/test_agent_loader.py::test_agent_def_max_concurrency_validation -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(core): add max_concurrency field to AgentDef"
```

---

## Task 2: Parse max_concurrency from agent frontmatter

**Files:**
- Modify: `src/picklebot/core/agent_loader.py:83-104`
- Test: `tests/core/test_agent_loader.py`

**Step 1: Write the failing test**

```python
# tests/core/test_agent_loader.py

def test_load_agent_with_max_concurrency(temp_agents_dir, shared_llm, tmp_path):
    """AgentLoader parses max_concurrency from frontmatter."""
    from picklebot.utils.config import Config
    from picklebot.core.agent_loader import AgentLoader

    # Create config with the temp agents dir
    config = Config(workspace=tmp_path, llm=shared_llm, default_agent="test")

    agent_dir = temp_agents_dir / "concurrent-agent"
    agent_dir.mkdir(parents=True)
    agent_md = agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Concurrent Agent
description: An agent with high concurrency
max_concurrency: 5
---
You are a concurrent assistant.
"""
    )

    loader = AgentLoader(config)
    agent_def = loader.load("concurrent-agent")

    assert agent_def.max_concurrency == 5


def test_load_agent_without_max_concurrency_uses_default(temp_agents_dir, shared_llm, tmp_path):
    """AgentLoader defaults max_concurrency to 1 if not specified."""
    from picklebot.utils.config import Config
    from picklebot.core.agent_loader import AgentLoader

    config = Config(workspace=tmp_path, llm=shared_llm, default_agent="test")

    agent_dir = temp_agents_dir / "default-agent"
    agent_dir.mkdir(parents=True)
    agent_md = agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Default Agent
description: An agent with default concurrency
---
You are a default assistant.
"""
    )

    loader = AgentLoader(config)
    agent_def = loader.load("default-agent")

    assert agent_def.max_concurrency == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_agent_loader.py::test_load_agent_with_max_concurrency -v`
Expected: FAIL with "AssertionError: assert 1 == 5"

**Step 3: Write minimal implementation**

```python
# src/picklebot/core/agent_loader.py
# Modify _parse_agent_def method:

def _parse_agent_def(
    self, def_id: str, frontmatter: dict[str, Any], body: str
) -> AgentDef:
    """Parse agent definition from frontmatter (callback for parse_definition)."""
    # Substitute template variables in body
    body = substitute_template(body, get_template_variables(self.config))

    # Extract nested llm config (optional)
    llm_overrides = frontmatter.get("llm")
    merged_llm = self._merge_llm_config(llm_overrides)

    try:
        return AgentDef(
            id=def_id,
            name=frontmatter["name"],  # type: ignore[misc]
            description=frontmatter.get("description", ""),
            system_prompt=body.strip(),
            llm=merged_llm,
            allow_skills=frontmatter.get("allow_skills", False),
            max_concurrency=frontmatter.get("max_concurrency", 1),  # NEW
        )
    except ValidationError as e:
        raise InvalidDefError("agent", def_id, str(e))
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_agent_loader.py::test_load_agent_with_max_concurrency tests/core/test_agent_loader.py::test_load_agent_without_max_concurrency_uses_default -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent_loader.py tests/core/test_agent_loader.py
git commit -m "feat(loader): parse max_concurrency from agent frontmatter"
```

---

## Task 3: Create SessionExecutor class

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Test: `tests/server/test_agent_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_agent_worker.py

# Add new imports at top:
from picklebot.server.agent_worker import SessionExecutor

@pytest.mark.anyio
async def test_session_executor_runs_session(test_context, tmp_path):
    """SessionExecutor runs a session successfully."""
    # Create a test agent definition
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test-agent"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---
You are a test assistant. Respond briefly.
"""
    )

    # Load the agent definition
    agent_def = test_context.agent_loader.load("test-agent")

    # Create a semaphore (value=1 for single concurrency)
    semaphore = asyncio.Semaphore(1)

    # Create a job
    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="Say hello",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    # Create queue for requeue
    queue: asyncio.Queue[Job] = asyncio.Queue()

    executor = SessionExecutor(test_context, agent_def, job, semaphore, queue)
    await executor.run()

    assert job.session_id is not None


@pytest.mark.anyio
async def test_session_executor_respects_semaphore(test_context, tmp_path):
    """SessionExecutor waits on semaphore before executing."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test-agent"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
---
You are a test assistant.
"""
    )

    agent_def = test_context.agent_loader.load("test-agent")

    # Create a semaphore with value 1
    semaphore = asyncio.Semaphore(1)

    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()

    # Acquire the semaphore first
    await semaphore.acquire()

    # Start executor - it should wait
    executor = SessionExecutor(test_context, agent_def, job, semaphore, queue)
    task = asyncio.create_task(executor.run())

    # Give it a moment to start waiting
    await asyncio.sleep(0.1)

    # Task should not be done (waiting on semaphore)
    assert not task.done()

    # Release semaphore
    semaphore.release()

    # Now task should complete
    await task

    # Clean up
    assert job.session_id is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_agent_worker.py::test_session_executor_runs_session -v`
Expected: FAIL with "cannot import name 'SessionExecutor'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/agent_worker.py
# Add SessionExecutor class after imports, before AgentWorker:

class SessionExecutor:
    """Executes a single agent session job."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        job: Job,
        semaphore: asyncio.Semaphore,
        agent_queue: asyncio.Queue[Job],
    ):
        self.context = context
        self.agent_def = agent_def
        self.job = job
        self.semaphore = semaphore
        self.agent_queue = agent_queue
        self.logger = logging.getLogger(f"picklebot.server.SessionExecutor.{agent_def.id}")

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
                    self.logger.warning(
                        f"Session {self.job.session_id} not found, creating new"
                    )
                    session = agent.new_session(self.job.mode, session_id=self.job.session_id)
            else:
                session = agent.new_session(self.job.mode)
                self.job.session_id = session.session_id

            await session.chat(self.job.message, self.job.frontend)
            self.logger.info(f"Session completed: {session.session_id}")

        except DefNotFoundError:
            self.logger.warning(f"Agent {self.agent_def.id} no longer exists")
        except Exception as e:
            self.logger.error(f"Session failed: {e}")
            self.job.message = "."
            await self.agent_queue.put(self.job)
```

**Step 4: Add import for logging and AgentDef**

```python
# src/picklebot/server/agent_worker.py
# Update imports at top:

import asyncio
import logging
from typing import TYPE_CHECKING

from picklebot.server.base import Worker, Job
from picklebot.core.agent import Agent
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py::test_session_executor_runs_session tests/server/test_agent_worker.py::test_session_executor_respects_semaphore -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/server/agent_worker.py tests/server/test_agent_worker.py
git commit -m "feat(server): add SessionExecutor class for session execution"
```

---

## Task 4: Refactor AgentWorker to AgentJobRouter

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Modify: `src/picklebot/server/server.py:10,50`
- Test: `tests/server/test_agent_worker.py`

**Step 1: Write the failing test**

```python
# tests/server/test_agent_worker.py

# Add import:
from picklebot.server.agent_worker import AgentJobRouter

@pytest.mark.anyio
async def test_agent_job_router_creates_semaphore_per_agent(test_context, tmp_path):
    """AgentJobRouter creates a semaphore for each agent on first job."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)

    # Create two test agents
    for agent_name in ["agent-a", "agent-b"]:
        agent_dir = agents_dir / agent_name
        agent_dir.mkdir(parents=True)
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text(
            f"""---
name: {agent_name}
max_concurrency: 2
---
You are {agent_name}.
"""
        )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    router = AgentJobRouter(test_context, queue)

    # Initially no semaphores
    assert len(router._semaphores) == 0

    # Create jobs for both agents
    job_a = Job(
        session_id=None,
        agent_id="agent-a",
        message="Test A",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    job_b = Job(
        session_id=None,
        agent_id="agent-b",
        message="Test B",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    await queue.put(job_a)
    await queue.put(job_b)

    # Process one job to trigger semaphore creation
    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    # Should have semaphore for agent-a
    assert "agent-a" in router._semaphores
    assert router._semaphores["agent-a"]._value == 2  # type: ignore

    # Process second job
    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    # Should have semaphores for both agents
    assert "agent-b" in router._semaphores
    assert router._semaphores["agent-b"]._value == 2  # type: ignore

    # Give tasks a moment to complete
    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_agent_job_router_concurrent_agents_dont_block(test_context, tmp_path):
    """AgentJobRouter allows concurrent agents to run without blocking each other."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)

    # Create two agents with concurrency 1 each
    for agent_name in ["agent-a", "agent-b"]:
        agent_dir = agents_dir / agent_name
        agent_dir.mkdir(parents=True)
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text(
            f"""---
name: {agent_name}
max_concurrency: 1
---
You are {agent_name}.
"""
        )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    router = AgentJobRouter(test_context, queue)

    # Create jobs for both agents
    job_a = Job(
        session_id=None,
        agent_id="agent-a",
        message="Test A",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    job_b = Job(
        session_id=None,
        agent_id="agent-b",
        message="Test B",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    await queue.put(job_a)
    await queue.put(job_b)

    # Dispatch both jobs
    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    # Both should be able to run concurrently (different agents)
    await asyncio.sleep(0.5)

    # Both sessions should be created
    assert job_a.session_id is not None
    assert job_b.session_id is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_agent_worker.py::test_agent_job_router_creates_semaphore_per_agent -v`
Expected: FAIL with "cannot import name 'AgentJobRouter'"

**Step 3: Write minimal implementation**

```python
# src/picklebot/server/agent_worker.py
# Replace AgentWorker class with AgentJobRouter:

class AgentJobRouter(Worker):
    """Routes jobs to session executors with per-agent concurrency control."""

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext", agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def run(self) -> None:
        """Process jobs sequentially, dispatch to executors."""
        self.logger.info("AgentJobRouter started")

        while True:
            job = await self.agent_queue.get()
            self._dispatch_job(job)
            self.agent_queue.task_done()
            self._maybe_cleanup_semaphores()

    def _dispatch_job(self, job: Job) -> None:
        """Create executor task for job."""
        try:
            agent_def = self.context.agent_loader.load(job.agent_id)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {job.agent_id}: {e}")
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(
            SessionExecutor(
                self.context, agent_def, job, sem, self.agent_queue
            ).run()
        )

    def _get_or_create_semaphore(self, agent_def: "AgentDef") -> asyncio.Semaphore:
        """Get existing or create new semaphore for agent."""
        if agent_def.id not in self._semaphores:
            self._semaphores[agent_def.id] = asyncio.Semaphore(
                agent_def.max_concurrency
            )
            self.logger.debug(
                f"Created semaphore for {agent_def.id} with value {agent_def.max_concurrency}"
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


# Keep AgentWorker as an alias for backward compatibility (optional, can remove later)
AgentWorker = AgentJobRouter
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py::test_agent_job_router_creates_semaphore_per_agent tests/server/test_agent_worker.py::test_agent_job_router_concurrent_agents_dont_block -v`
Expected: PASS

**Step 5: Update server.py to use AgentJobRouter**

```python
# src/picklebot/server/server.py
# Update import:
from picklebot.server.agent_worker import AgentJobRouter

# Update _setup_workers method (line 50):
def _setup_workers(self) -> None:
    """Create all workers."""
    self.workers.append(AgentJobRouter(self.context, self.agent_queue))
    self.workers.append(CronWorker(self.context, self.agent_queue))
    # ... rest unchanged
```

**Step 6: Run all tests to ensure nothing broke**

Run: `uv run pytest tests/server/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add src/picklebot/server/agent_worker.py src/picklebot/server/server.py tests/server/test_agent_worker.py
git commit -m "feat(server): replace AgentWorker with AgentJobRouter + semaphores"
```

---

## Task 5: Update existing tests for new architecture

**Files:**
- Modify: `tests/server/test_agent_worker.py`

**Step 1: Update test_agent_worker_processes_job**

The existing test uses `worker._process_job()` which no longer exists. Update to use new dispatch method:

```python
# tests/server/test_agent_worker.py

@pytest.mark.anyio
async def test_agent_worker_processes_job(test_context, tmp_path):
    """AgentJobRouter processes a job from the queue."""
    # Create a test agent definition
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test-agent"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---
You are a test assistant. Respond briefly.
"""
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    router = AgentJobRouter(test_context, queue)

    # Create a job
    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="Say hello",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await queue.put(job)

    # Dispatch the job
    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    # Give the task a moment to complete
    await asyncio.sleep(0.5)

    assert job.session_id is not None  # Session created
```

**Step 2: Update test_agent_worker_does_not_requeue_nonexistent_agent**

```python
@pytest.mark.anyio
async def test_agent_job_router_does_not_requeue_nonexistent_agent(test_context):
    """AgentJobRouter does not requeue job when agent doesn't exist (DefNotFoundError)."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    router = AgentJobRouter(test_context, queue)

    # Create a job with invalid agent (will raise DefNotFoundError)
    job = Job(
        session_id=None,
        agent_id="nonexistent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await queue.put(job)

    # Dispatch should fail but NOT requeue
    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    # Job should NOT be modified or requeued
    assert job.message == "Test"  # Original message unchanged
    assert queue.empty()  # Job was not put back in queue
```

**Step 3: Update test_agent_worker_requeues_on_transient_error**

The transient error test needs to verify SessionExecutor requeues on error:

```python
@pytest.mark.anyio
async def test_session_executor_requeues_on_transient_error(test_context, tmp_path):
    """SessionExecutor requeues job with '.' message on transient errors."""
    # Create a test agent definition
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test-agent"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---
You are a test assistant.
"""
    )

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    # Create a job with a frontend that raises a transient error
    class ErrorFrontend(FakeFrontend):
        async def show_message(self, content: str, agent_id: str | None = None) -> None:
            raise RuntimeError("Transient error")

    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="Test",
        frontend=ErrorFrontend(),
        mode=SessionMode.CHAT,
    )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    executor = SessionExecutor(test_context, agent_def, job, semaphore, queue)

    await executor.run()

    # Job should be requeued with message = "."
    assert job.message == "."
    assert not queue.empty()  # Job was put back in queue
```

**Step 4: Update test_agent_worker_recovers_missing_session**

```python
@pytest.mark.anyio
async def test_session_executor_recovers_missing_session(test_context, tmp_path):
    """SessionExecutor creates new session with same ID if session not found in history."""
    # Create a test agent definition
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    test_agent_dir = agents_dir / "test-agent"
    test_agent_dir.mkdir(parents=True)

    agent_md = test_agent_dir / "AGENT.md"
    agent_md.write_text(
        """---
name: Test Agent
description: A test agent
---
You are a test assistant.
"""
    )

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)
    queue: asyncio.Queue[Job] = asyncio.Queue()

    # Create a job with a session_id that doesn't exist in history
    nonexistent_session_id = "nonexistent-session-uuid"
    job = Job(
        session_id=nonexistent_session_id,
        agent_id="test-agent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    executor = SessionExecutor(test_context, agent_def, job, semaphore, queue)
    await executor.run()

    # Session should be created with the provided ID in history
    assert job.session_id == nonexistent_session_id
    session_ids = [s.id for s in test_context.history_store.list_sessions()]
    assert nonexistent_session_id in session_ids
```

**Step 5: Run all tests to verify they pass**

Run: `uv run pytest tests/server/test_agent_worker.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add tests/server/test_agent_worker.py
git commit -m "test(server): update tests for AgentJobRouter architecture"
```

---

## Task 6: Add semaphore cleanup test

**Files:**
- Modify: `tests/server/test_agent_worker.py`

**Step 1: Write the test**

```python
@pytest.mark.anyio
async def test_semaphore_cleanup_removes_stale_semaphores(test_context, tmp_path):
    """AgentJobRouter removes semaphores for deleted agents when threshold exceeded."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)

    # Create 6 agents (exceeds CLEANUP_THRESHOLD of 5)
    for i in range(6):
        agent_dir = agents_dir / f"agent-{i}"
        agent_dir.mkdir(parents=True)
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text(
            f"""---
name: Agent {i}
---
You are agent {i}.
"""
        )

    queue: asyncio.Queue[Job] = asyncio.Queue()
    router = AgentJobRouter(test_context, queue)

    # Dispatch jobs for all agents to create semaphores
    for i in range(6):
        job = Job(
            session_id=None,
            agent_id=f"agent-{i}",
            message="Test",
            frontend=FakeFrontend(),
            mode=SessionMode.CHAT,
        )
        await queue.put(job)
        j = await queue.get()
        router._dispatch_job(j)
        queue.task_done()

    await asyncio.sleep(0.3)  # Let tasks start

    # All 6 semaphores should exist
    assert len(router._semaphores) == 6

    # Delete agent-5
    import shutil
    shutil.rmtree(agents_dir / "agent-5")

    # Trigger cleanup by dispatching another job
    job = Job(
        session_id=None,
        agent_id="agent-0",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await queue.put(job)
    j = await queue.get()
    router._dispatch_job(j)
    queue.task_done()

    # agent-5 semaphore should be cleaned up
    assert "agent-5" not in router._semaphores
    assert len(router._semaphores) == 5
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py::test_semaphore_cleanup_removes_stale_semaphores -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/server/test_agent_worker.py
git commit -m "test(server): add semaphore cleanup test"
```

---

## Task 7: Update agents with max_concurrency

**Files:**
- Modify: `agents/pickle/AGENT.md`

**Step 1: Add max_concurrency to pickle agent**

```yaml
# agents/pickle/AGENT.md
# Add to frontmatter:

---
name: Pickle
description: General-purpose assistant for coding, research, and tasks
llm:
  temperature: 0.7
max_concurrency: 3  # NEW: Allow 3 concurrent sessions
---
```

**Step 2: Verify agent loads correctly**

Run: `uv run python -c "from picklebot.core.agent_loader import AgentLoader; from picklebot.utils.config import Config; c = Config.load(); l = AgentLoader(c); a = l.load('pickle'); print(f'max_concurrency: {a.max_concurrency}')"`
Expected: `max_concurrency: 3`

**Step 3: Commit**

```bash
git add agents/pickle/AGENT.md
git commit -m "feat(agents): set pickle max_concurrency to 3"
```

---

## Task 8: Run full test suite and format

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All PASS

**Step 2: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Final commit if any formatting changes**

```bash
git add -A
git commit -m "style: format and lint after agent concurrency refactor"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Add max_concurrency to AgentDef | `agent_loader.py` |
| 2 | Parse max_concurrency from frontmatter | `agent_loader.py` |
| 3 | Create SessionExecutor class | `agent_worker.py` |
| 4 | Refactor AgentWorker to AgentJobRouter | `agent_worker.py`, `server.py` |
| 5 | Update existing tests | `test_agent_worker.py` |
| 6 | Add semaphore cleanup test | `test_agent_worker.py` |
| 7 | Update pickle agent | `agents/pickle/AGENT.md` |
| 8 | Run tests, format, lint | All |
