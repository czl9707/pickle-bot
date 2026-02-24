"""Tests for AgentDispatcherWorker and SessionExecutor."""

import asyncio
import shutil
from contextlib import asynccontextmanager
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend
from picklebot.server.agent_worker import (
    MAX_RETRIES,
    AgentDispatcherWorker,
    SessionExecutor,
)
from picklebot.server.base import Job


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
    """AgentDispatcherWorker processes a job from the queue."""
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

    router = AgentDispatcherWorker(test_context)

    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="Say hello",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await test_context.agent_queue.put(job)

    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    await asyncio.sleep(0.5)

    assert job.session_id is not None


@pytest.mark.anyio
async def test_agent_job_router_does_not_requeue_nonexistent_agent(test_context):
    """AgentDispatcherWorker does not requeue job when agent doesn't exist."""
    router = AgentDispatcherWorker(test_context)

    job = Job(
        session_id=None,
        agent_id="nonexistent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await test_context.agent_queue.put(job)

    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    assert job.message == "Test"
    assert test_context.agent_queue.empty()


@pytest.mark.anyio
async def test_session_executor_requeues_on_transient_error(test_context, tmp_path):
    """SessionExecutor requeues job with '.' message on transient errors."""
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

    executor = SessionExecutor(test_context, agent_def, job, semaphore)

    await executor.run()

    assert job.message == "."
    assert not test_context.agent_queue.empty()


@pytest.mark.anyio
async def test_session_executor_recovers_missing_session(test_context, tmp_path):
    """SessionExecutor creates new session with same ID if session not found."""
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

    nonexistent_session_id = "nonexistent-session-uuid"
    job = Job(
        session_id=nonexistent_session_id,
        agent_id="test-agent",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )

    executor = SessionExecutor(test_context, agent_def, job, semaphore)
    await executor.run()

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

    executor = SessionExecutor(test_context, agent_def, job, semaphore)
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

    # Acquire the semaphore first
    await semaphore.acquire()

    # Start executor - it should wait
    executor = SessionExecutor(test_context, agent_def, job, semaphore)
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
    """AgentDispatcherWorker creates a semaphore for each agent on first job."""
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

    router = AgentDispatcherWorker(test_context)

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

    await test_context.agent_queue.put(job_a)
    await test_context.agent_queue.put(job_b)

    # Process one job to trigger semaphore creation
    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    # Should have semaphore for agent-a
    assert "agent-a" in router._semaphores
    assert router._semaphores["agent-a"]._value == 2  # type: ignore

    # Process second job
    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    # Should have semaphores for both agents
    assert "agent-b" in router._semaphores
    assert router._semaphores["agent-b"]._value == 2  # type: ignore

    # Give tasks a moment to complete
    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_agent_job_router_concurrent_agents_dont_block(test_context, tmp_path):
    """AgentDispatcherWorker allows concurrent agents to run without blocking each other."""
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

    router = AgentDispatcherWorker(test_context)

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

    await test_context.agent_queue.put(job_a)
    await test_context.agent_queue.put(job_b)

    # Dispatch both jobs
    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    # Both should be able to run concurrently (different agents)
    await asyncio.sleep(0.5)

    # Both sessions should be created
    assert job_a.session_id is not None
    assert job_b.session_id is not None


@pytest.mark.anyio
async def test_semaphore_cleanup_removes_stale_semaphores(test_context, tmp_path):
    """AgentDispatcherWorker removes semaphores for deleted agents when threshold exceeded."""
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

    router = AgentDispatcherWorker(test_context)

    # Dispatch jobs for all agents to create semaphores
    for i in range(6):
        job = Job(
            session_id=None,
            agent_id=f"agent-{i}",
            message="Test",
            frontend=FakeFrontend(),
            mode=SessionMode.CHAT,
        )
        await test_context.agent_queue.put(job)
        j = await test_context.agent_queue.get()
        router._dispatch_job(j)
        test_context.agent_queue.task_done()

    await asyncio.sleep(0.3)  # Let tasks start

    # All 6 semaphores should exist
    assert len(router._semaphores) == 6

    # Delete agent-5
    shutil.rmtree(agents_dir / "agent-5")

    # Trigger cleanup by dispatching another job
    job = Job(
        session_id=None,
        agent_id="agent-0",
        message="Test",
        frontend=FakeFrontend(),
        mode=SessionMode.CHAT,
    )
    await test_context.agent_queue.put(job)
    j = await test_context.agent_queue.get()
    router._dispatch_job(j)
    test_context.agent_queue.task_done()

    # Call cleanup explicitly (in run() this happens after task_done())
    router._maybe_cleanup_semaphores()

    # agent-5 semaphore should be cleaned up
    assert "agent-5" not in router._semaphores
    assert len(router._semaphores) == 5


# ============================================================================
# Tests for Task 3: result future and retry logic
# ============================================================================


@pytest.mark.anyio
async def test_session_executor_sets_result_on_success(test_context, tmp_path):
    """SessionExecutor should set result on future when session succeeds."""
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

    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="hello",
        frontend=SilentFrontend(),
        mode=SessionMode.CHAT,
    )
    job.result_future = asyncio.Future()  # Create future in async context

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        mock_session = AsyncMock()
        mock_session.chat = AsyncMock(return_value="response text")
        mock_session.session_id = "session-123"

        mock_agent = MagicMock()
        mock_agent.new_session.return_value = mock_session
        MockAgent.return_value = mock_agent

        executor = SessionExecutor(test_context, agent_def, job, semaphore)
        await executor.run()

    assert job.result_future.done()
    assert job.result_future.result() == "response text"


@pytest.mark.anyio
async def test_session_executor_requeues_on_first_failure(test_context, tmp_path):
    """SessionExecutor should requeue job with incremented retry_count on failure."""
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

    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="hello",
        frontend=SilentFrontend(),
        mode=SessionMode.CHAT,
        retry_count=0,
    )
    job.result_future = asyncio.Future()

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("boom")

        executor = SessionExecutor(test_context, agent_def, job, semaphore)
        await executor.run()

    # Job should be requeued
    requeued_job = await test_context.agent_queue.get()
    assert requeued_job.retry_count == 1
    assert requeued_job.message == "."


@pytest.mark.anyio
async def test_session_executor_sets_exception_after_max_retries(
    test_context, tmp_path
):
    """SessionExecutor should set exception after MAX_RETRIES failures."""
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

    job = Job(
        session_id=None,
        agent_id="test-agent",
        message="hello",
        frontend=SilentFrontend(),
        mode=SessionMode.CHAT,
        retry_count=MAX_RETRIES,  # Already at max
    )
    job.result_future = asyncio.Future()

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("final boom")

        executor = SessionExecutor(test_context, agent_def, job, semaphore)
        await executor.run()

    assert job.result_future.done()
    assert isinstance(job.result_future.exception(), Exception)
    assert str(job.result_future.exception()) == "final boom"

    # Should NOT be requeued
    assert test_context.agent_queue.empty()


# ============================================================================
# Tests for Task 4: AgentDispatcherWorker uses context.agent_queue
# ============================================================================


@pytest.mark.anyio
async def test_agent_dispatcher_uses_context_queue():
    """AgentDispatcherWorker should get queue from context."""
    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.agent_loader.discover_agents.return_value = []

    dispatcher = AgentDispatcherWorker(context)

    # Should not have its own agent_queue attribute separate from context
    assert (
        not hasattr(dispatcher, "agent_queue")
        or dispatcher.agent_queue is context.agent_queue
    )
