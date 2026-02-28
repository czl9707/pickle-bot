"""Tests for AgentDispatcherWorker and SessionExecutor."""

import asyncio
import shutil
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.core.agent import SessionMode
from picklebot.server.agent_worker import (
    MAX_RETRIES,
    AgentDispatcherWorker,
    SessionExecutor,
)
from picklebot.server.base import Job
from picklebot.events.types import EventType, Event


@pytest.mark.anyio
async def test_agent_worker_processes_job(test_context, tmp_path):
    """AgentDispatcherWorker processes a job from event."""
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
        agent_id="test-agent",
        message="Say hello",
        mode=SessionMode.CHAT,
    )
    router._dispatch_job(job)

    await asyncio.sleep(0.5)

    assert job.session_id is not None


@pytest.mark.anyio
async def test_agent_job_router_does_not_requeue_nonexistent_agent(test_context):
    """AgentDispatcherWorker does not requeue job when agent doesn't exist."""
    router = AgentDispatcherWorker(test_context)

    # Create a future to track the error
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    test_context.register_future("test-job-id", future)

    job = Job(
        job_id="test-job-id",
        agent_id="nonexistent",
        message="Test",
        mode=SessionMode.CHAT,
    )
    router._dispatch_job(job)

    # Future should have exception set
    assert future.done()
    assert future.exception() is not None


@pytest.mark.anyio
async def test_session_executor_requeues_on_transient_error(test_context, tmp_path):
    """SessionExecutor requeues job via INBOUND event on transient errors."""
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
        agent_id="test-agent",
        message="Test",
        mode=SessionMode.CHAT,
    )

    # Track inbound events for retry
    inbound_events: list[Event] = []

    async def capture_event(event: Event) -> None:
        inbound_events.append(event)

    test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    executor = SessionExecutor(test_context, agent_def, job, semaphore)

    # Mock the Agent to raise an error
    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = RuntimeError("Transient error")
        await executor.run()

    assert job.message == "."
    assert len(inbound_events) == 1
    assert inbound_events[0].type == EventType.INBOUND
    assert inbound_events[0].metadata is not None
    assert inbound_events[0].metadata["retry_count"] == 1


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
        agent_id="test-agent",
        message="Say hello",
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
        agent_id="test-agent",
        message="Test",
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
        agent_id="agent-a",
        message="Test A",
        mode=SessionMode.CHAT,
    )
    job_b = Job(
        agent_id="agent-b",
        message="Test B",
        mode=SessionMode.CHAT,
    )

    router._dispatch_job(job_a)

    # Should have semaphore for agent-a
    assert "agent-a" in router._semaphores
    assert router._semaphores["agent-a"]._value == 2  # type: ignore

    router._dispatch_job(job_b)

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
        agent_id="agent-a",
        message="Test A",
        mode=SessionMode.CHAT,
    )
    job_b = Job(
        agent_id="agent-b",
        message="Test B",
        mode=SessionMode.CHAT,
    )

    router._dispatch_job(job_a)
    router._dispatch_job(job_b)

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
            agent_id=f"agent-{i}",
            message="Test",
            mode=SessionMode.CHAT,
        )
        router._dispatch_job(job)

    await asyncio.sleep(0.3)  # Let tasks start

    # All 6 semaphores should exist
    assert len(router._semaphores) == 6

    # Delete agent-5
    shutil.rmtree(agents_dir / "agent-5")

    # Trigger cleanup by dispatching another job
    job = Job(
        agent_id="agent-0",
        message="Test",
        mode=SessionMode.CHAT,
    )
    router._dispatch_job(job)

    # Call cleanup explicitly (in run() this happens after sleep)
    router._maybe_cleanup_semaphores()

    # agent-5 semaphore should be cleaned up
    assert "agent-5" not in router._semaphores
    assert len(router._semaphores) == 5


# ============================================================================
# Tests for result future and retry logic
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
        agent_id="test-agent",
        message="hello",
        mode=SessionMode.CHAT,
    )

    # Register a future for this job
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    test_context.register_future(job.job_id, future)

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        mock_session = AsyncMock()
        mock_session.chat = AsyncMock(return_value="response text")
        mock_session.session_id = "session-123"

        mock_agent = MagicMock()
        mock_agent.new_session.return_value = mock_session
        MockAgent.return_value = mock_agent

        executor = SessionExecutor(test_context, agent_def, job, semaphore)
        await executor.run()

    assert future.done()
    assert future.result() == "response text"


@pytest.mark.anyio
async def test_session_executor_requeues_on_first_failure(test_context, tmp_path):
    """SessionExecutor should requeue job via event with incremented retry_count on failure."""
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
        agent_id="test-agent",
        message="hello",
        mode=SessionMode.CHAT,
        retry_count=0,
    )

    # Track inbound events for retry
    inbound_events: list[Event] = []

    async def capture_event(event: Event) -> None:
        inbound_events.append(event)

    test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("boom")

        executor = SessionExecutor(test_context, agent_def, job, semaphore)
        await executor.run()

    # Job should be requeued via INBOUND event
    assert len(inbound_events) == 1
    retry_event = inbound_events[0]
    assert retry_event.type == EventType.INBOUND
    assert retry_event.metadata is not None
    assert retry_event.metadata["retry_count"] == 1
    assert retry_event.content == "."


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
        agent_id="test-agent",
        message="hello",
        mode=SessionMode.CHAT,
        retry_count=MAX_RETRIES,  # Already at max
    )

    # Register a future for this job
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()
    test_context.register_future(job.job_id, future)

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("final boom")

        executor = SessionExecutor(test_context, agent_def, job, semaphore)
        await executor.run()

    assert future.done()
    assert isinstance(future.exception(), Exception)
    assert str(future.exception()) == "final boom"


# ============================================================================
# Tests for AgentDispatcherWorker event handling
# ============================================================================


@pytest.mark.anyio
async def test_agent_dispatcher_handles_inbound_event(test_context):
    """AgentDispatcherWorker should handle INBOUND events."""
    router = AgentDispatcherWorker(test_context)

    # Track dispatched jobs
    dispatched_jobs: list[Job] = []

    def capture_dispatch(job: Job) -> None:
        dispatched_jobs.append(job)
        # Don't actually execute, just capture

    router._dispatch_job = capture_dispatch  # type: ignore

    event = Event(
        type=EventType.INBOUND,
        session_id="test-session",
        content="Hello world",
        source="test:platform",
        timestamp=time.time(),
    )

    await router.handle_inbound(event)

    assert len(dispatched_jobs) == 1
    job = dispatched_jobs[0]
    assert job.message == "Hello world"
    assert job.session_id == "test-session"
    assert job.mode == SessionMode.CHAT


@pytest.mark.anyio
async def test_agent_dispatcher_handles_dispatch_event(test_context):
    """AgentDispatcherWorker should handle DISPATCH events."""
    router = AgentDispatcherWorker(test_context)

    # Track dispatched jobs
    dispatched_jobs: list[Job] = []

    def capture_dispatch(job: Job) -> None:
        dispatched_jobs.append(job)

    router._dispatch_job = capture_dispatch  # type: ignore

    event = Event(
        type=EventType.DISPATCH,
        session_id="job-session",
        content="Run task",
        source="test:cron",
        timestamp=time.time(),
        metadata={
            "job_id": "test-job-123",
            "agent_id": "test-agent",
            "mode": "JOB",
        },
    )

    await router.handle_dispatch(event)

    assert len(dispatched_jobs) == 1
    job = dispatched_jobs[0]
    assert job.job_id == "test-job-123"
    assert job.agent_id == "test-agent"
    assert job.message == "Run task"
    assert job.mode == SessionMode.JOB
