"""Tests for AgentDispatcherWorker and SessionExecutor."""

import asyncio
import shutil
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from picklebot.core.agent import SessionMode
from picklebot.server.agent_worker import (
    MAX_RETRIES,
    AgentDispatcherWorker,
    SessionExecutor,
)
from picklebot.events.types import EventType, Event


def make_event(
    content: str = "Test",
    session_id: str | None = None,
    agent_id: str = "test-agent",
    mode: SessionMode = SessionMode.CHAT,
    job_id: str | None = None,
    retry_count: int = 0,
    event_type: EventType = EventType.INBOUND,
) -> Event:
    """Helper to create an event for testing."""
    return Event(
        type=event_type,
        session_id=session_id or "",
        content=content,
        source="test:platform",
        timestamp=time.time(),
        metadata={
            "job_id": job_id or str(uuid.uuid4()),
            "agent_id": agent_id,
            "mode": mode.value,
            "retry_count": retry_count,
        },
    )


@pytest.mark.anyio
async def test_agent_worker_processes_event(test_context, tmp_path):
    """AgentDispatcherWorker processes an event."""
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

    event = make_event(content="Say hello", agent_id="test-agent")
    router._dispatch_event(event)

    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_agent_router_publishes_error_for_nonexistent_agent(test_context):
    """AgentDispatcherWorker publishes RESULT with error when agent doesn't exist."""
    router = AgentDispatcherWorker(test_context)

    # Track RESULT events
    result_events: list[Event] = []

    async def capture_result(event: Event) -> None:
        result_events.append(event)

    test_context.eventbus.subscribe(EventType.DISPATCH_RESULT, capture_result)

    event = make_event(agent_id="nonexistent", job_id="test-job-id")
    router._dispatch_event(event)

    # Wait for async error result to be published
    await asyncio.sleep(0.1)

    # Should have published RESULT with error
    assert len(result_events) == 1
    result_event = result_events[0]
    assert result_event.type == EventType.DISPATCH_RESULT
    assert result_event.metadata.get("job_id") == "test-job-id"
    assert "error" in result_event.metadata
    assert "nonexistent" in result_event.metadata["error"]


@pytest.mark.anyio
async def test_session_executor_requeues_on_transient_error(test_context, tmp_path):
    """SessionExecutor requeues via INBOUND event on transient errors."""
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

    event = make_event(content="Test", agent_id="test-agent")

    # Track inbound events for retry
    inbound_events: list[Event] = []

    async def capture_event(evt: Event) -> None:
        inbound_events.append(evt)

    test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    executor = SessionExecutor(test_context, agent_def, event, semaphore)

    # Mock the Agent to raise an error
    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = RuntimeError("Transient error")
        await executor.run()

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
    event = make_event(
        content="Test", session_id=nonexistent_session_id, agent_id="test-agent"
    )

    executor = SessionExecutor(test_context, agent_def, event, semaphore)
    await executor.run()

    session_ids = [s.id for s in test_context.history_store.list_sessions()]
    assert nonexistent_session_id in session_ids


@pytest.mark.anyio
async def test_session_executor_runs_session(test_context, tmp_path):
    """SessionExecutor runs a session successfully."""
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

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_event(content="Say hello", agent_id="test-agent")

    executor = SessionExecutor(test_context, agent_def, event, semaphore)
    await executor.run()


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
    semaphore = asyncio.Semaphore(1)

    event = make_event(content="Test", agent_id="test-agent")

    # Acquire the semaphore first
    await semaphore.acquire()

    # Start executor - it should wait
    executor = SessionExecutor(test_context, agent_def, event, semaphore)
    task = asyncio.create_task(executor.run())

    # Give it a moment to start waiting
    await asyncio.sleep(0.1)

    # Task should not be done (waiting on semaphore)
    assert not task.done()

    # Release semaphore
    semaphore.release()

    # Now task should complete
    await task


@pytest.mark.anyio
async def test_agent_router_creates_semaphore_per_agent(test_context, tmp_path):
    """AgentDispatcherWorker creates a semaphore for each agent on first event."""
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

    event_a = make_event(content="Test A", agent_id="agent-a")
    event_b = make_event(content="Test B", agent_id="agent-b")

    router._dispatch_event(event_a)

    # Should have semaphore for agent-a
    assert "agent-a" in router._semaphores
    assert router._semaphores["agent-a"]._value == 2  # type: ignore

    router._dispatch_event(event_b)

    # Should have semaphores for both agents
    assert "agent-b" in router._semaphores
    assert router._semaphores["agent-b"]._value == 2  # type: ignore

    # Give tasks a moment to complete
    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_agent_router_concurrent_agents_dont_block(test_context, tmp_path):
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

    event_a = make_event(content="Test A", agent_id="agent-a")
    event_b = make_event(content="Test B", agent_id="agent-b")

    router._dispatch_event(event_a)
    router._dispatch_event(event_b)

    # Both should be able to run concurrently (different agents)
    await asyncio.sleep(0.5)


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

    # Dispatch events for all agents to create semaphores
    for i in range(6):
        event = make_event(content="Test", agent_id=f"agent-{i}")
        router._dispatch_event(event)

    await asyncio.sleep(0.3)  # Let tasks start

    # All 6 semaphores should exist
    assert len(router._semaphores) == 6

    # Delete agent-5
    shutil.rmtree(agents_dir / "agent-5")

    # Trigger cleanup by dispatching another event
    event = make_event(content="Test", agent_id="agent-0")
    router._dispatch_event(event)

    # Call cleanup explicitly (in run() this happens after sleep)
    router._maybe_cleanup_semaphores()

    # agent-5 semaphore should be cleaned up
    assert "agent-5" not in router._semaphores
    assert len(router._semaphores) == 5


# ============================================================================
# Tests for RESULT event and retry logic
# ============================================================================


@pytest.mark.anyio
async def test_session_executor_publishes_result_on_success(test_context, tmp_path):
    """SessionExecutor should publish RESULT event when session succeeds."""
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

    event = make_event(content="hello", agent_id="test-agent", job_id="test-job-123")

    # Track RESULT events
    result_events: list[Event] = []

    async def capture_result(evt: Event) -> None:
        result_events.append(evt)

    test_context.eventbus.subscribe(EventType.DISPATCH_RESULT, capture_result)

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        mock_session = AsyncMock()
        mock_session.chat = AsyncMock(return_value="response text")
        mock_session.session_id = "session-123"

        mock_agent = MagicMock()
        mock_agent.new_session.return_value = mock_session
        MockAgent.return_value = mock_agent

        executor = SessionExecutor(test_context, agent_def, event, semaphore)
        await executor.run()

    assert len(result_events) == 1
    result_event = result_events[0]
    assert result_event.type == EventType.DISPATCH_RESULT
    assert result_event.content == "response text"
    assert result_event.metadata.get("job_id") == "test-job-123"


@pytest.mark.anyio
async def test_session_executor_requeues_on_first_failure(test_context, tmp_path):
    """SessionExecutor should requeue via event with incremented retry_count on failure."""
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

    event = make_event(content="hello", agent_id="test-agent", retry_count=0)

    # Track inbound events for retry
    inbound_events: list[Event] = []

    async def capture_event(evt: Event) -> None:
        inbound_events.append(evt)

    test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("boom")

        executor = SessionExecutor(test_context, agent_def, event, semaphore)
        await executor.run()

    # Should be requeued via INBOUND event
    assert len(inbound_events) == 1
    retry_event = inbound_events[0]
    assert retry_event.type == EventType.INBOUND
    assert retry_event.metadata is not None
    assert retry_event.metadata["retry_count"] == 1
    assert retry_event.content == "."


@pytest.mark.anyio
async def test_session_executor_publishes_result_with_error_after_max_retries(
    test_context, tmp_path
):
    """SessionExecutor should publish RESULT event with error after MAX_RETRIES failures."""
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

    event = make_event(
        content="hello",
        agent_id="test-agent",
        retry_count=MAX_RETRIES,
        job_id="job-456",
    )

    # Track RESULT events
    result_events: list[Event] = []

    async def capture_result(evt: Event) -> None:
        result_events.append(evt)

    test_context.eventbus.subscribe(EventType.DISPATCH_RESULT, capture_result)

    with patch("picklebot.server.agent_worker.Agent") as MockAgent:
        MockAgent.side_effect = Exception("final boom")

        executor = SessionExecutor(test_context, agent_def, event, semaphore)
        await executor.run()

    assert len(result_events) == 1
    result_event = result_events[0]
    assert result_event.type == EventType.DISPATCH_RESULT
    assert result_event.metadata.get("job_id") == "job-456"
    assert "error" in result_event.metadata
    assert result_event.metadata["error"] == "final boom"


# ============================================================================
# Tests for AgentDispatcherWorker event handling
# ============================================================================


@pytest.mark.anyio
async def test_agent_dispatcher_handles_inbound_event(test_context):
    """AgentDispatcherWorker should handle INBOUND events."""
    router = AgentDispatcherWorker(test_context)

    # Track dispatched events
    dispatched_events: list[Event] = []

    def capture_dispatch(evt: Event) -> None:
        dispatched_events.append(evt)
        # Don't actually execute, just capture

    router._dispatch_event = capture_dispatch  # type: ignore

    event = Event(
        type=EventType.INBOUND,
        session_id="test-session",
        content="Hello world",
        source="test:platform",
        timestamp=time.time(),
    )

    await router.handle_inbound(event)

    assert len(dispatched_events) == 1
    dispatched = dispatched_events[0]
    assert dispatched.content == "Hello world"
    assert dispatched.session_id == "test-session"


@pytest.mark.anyio
async def test_agent_dispatcher_handles_dispatch_event(test_context):
    """AgentDispatcherWorker should handle DISPATCH events."""
    router = AgentDispatcherWorker(test_context)

    # Track dispatched events
    dispatched_events: list[Event] = []

    def capture_dispatch(evt: Event) -> None:
        dispatched_events.append(evt)

    router._dispatch_event = capture_dispatch  # type: ignore

    event = Event(
        type=EventType.DISPATCH,
        session_id="job-session",
        content="Run task",
        source="agent:caller",
        timestamp=time.time(),
        metadata={
            "job_id": "test-job-123",
            "agent_id": "test-agent",
            "mode": "JOB",
        },
    )

    await router.handle_dispatch(event)

    assert len(dispatched_events) == 1
    dispatched = dispatched_events[0]
    assert dispatched.metadata.get("job_id") == "test-job-123"
    assert dispatched.metadata.get("agent_id") == "test-agent"
    assert dispatched.content == "Run task"
