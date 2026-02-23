"""Tests for AgentWorker."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest

from picklebot.server.base import Job
from picklebot.server.agent_worker import AgentWorker, SessionExecutor, AgentJobRouter
from picklebot.core.agent import SessionMode


class FakeFrontend:
    """Fake frontend for testing."""

    def __init__(self):
        self.messages: list[str] = []

    async def show_message(self, content: str, agent_id: str | None = None) -> None:
        self.messages.append(content)

    async def show_welcome(self) -> None:
        pass

    async def show_system_message(self, content: str) -> None:
        pass

    @asynccontextmanager
    async def show_transient(self, content: str) -> AsyncIterator[None]:
        yield

    @asynccontextmanager
    async def show_dispatch(
        self, calling_agent: str, target_agent: str, task: str
    ) -> AsyncIterator[None]:
        yield


@pytest.mark.anyio
async def test_agent_worker_processes_job(test_context, tmp_path):
    """AgentWorker processes a job from the queue."""
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
    worker = AgentWorker(test_context, queue)

    # Create a job
    job = Job(
        session_id=None,
        agent_id="test-agent",
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


@pytest.mark.anyio
async def test_agent_worker_does_not_requeue_nonexistent_agent(test_context):
    """AgentWorker does not requeue job when agent doesn't exist (DefNotFoundError)."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = AgentWorker(test_context, queue)

    # Create a job with invalid agent (will raise DefNotFoundError)
    job = Job(
        session_id=None,
        agent_id="nonexistent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await queue.put(job)

    # Process should fail but NOT requeue (DefNotFoundError is non-recoverable)
    await queue.get()
    await worker._process_job(job)

    # Job should NOT be modified or requeued
    assert job.message == "Test"  # Original message unchanged
    assert queue.empty()  # Job was not put back in queue


@pytest.mark.anyio
async def test_agent_worker_requeues_on_transient_error(test_context, tmp_path):
    """AgentWorker requeues job with '.' message on transient errors."""
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

    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = AgentWorker(test_context, queue)

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
    await queue.put(job)

    # Process should fail and requeue (transient error)
    await queue.get()
    await worker._process_job(job)

    # Job should be requeued with message = "."
    assert job.message == "."
    assert not queue.empty()  # Job was put back in queue


@pytest.mark.anyio
async def test_agent_worker_recovers_missing_session(test_context, tmp_path):
    """AgentWorker creates new session with same ID if session not found in history."""
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

    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = AgentWorker(test_context, queue)

    # Create a job with a session_id that doesn't exist in history
    nonexistent_session_id = "nonexistent-session-uuid"
    job = Job(
        session_id=nonexistent_session_id,
        agent_id="test-agent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    await worker._process_job(job)

    # Session should be created with the provided ID in history
    assert job.session_id == nonexistent_session_id
    session_ids = [s.id for s in test_context.history_store.list_sessions()]
    assert nonexistent_session_id in session_ids


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
