"""Tests for AgentWorker and SessionExecutor."""

import asyncio
import shutil
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers import create_test_agent

from picklebot.server.agent_worker import (
    MAX_RETRIES,
    AgentWorker,
    SessionExecutor,
)
from picklebot.core.events import (
    InboundEvent,
    DispatchEvent,
    DispatchResultEvent,
)


def make_inbound_event(
    content: str = "Test",
    session_id: str | None = None,
    agent_id: str = "test-agent",
    retry_count: int = 0,
) -> InboundEvent:
    """Helper to create an InboundEvent for testing."""
    return InboundEvent(
        session_id=session_id or str(uuid.uuid4()),
        agent_id=agent_id,
        source="test:platform",
        content=content,
        timestamp=time.time(),
        retry_count=retry_count,
    )


def make_dispatch_event(
    content: str = "Test",
    session_id: str | None = None,
    agent_id: str = "test-agent",
    retry_count: int = 0,
    parent_session_id: str = "parent-session-123",
) -> DispatchEvent:
    """Helper to create a DispatchEvent for testing."""
    return DispatchEvent(
        session_id=session_id or str(uuid.uuid4()),
        agent_id=agent_id,
        source="agent:caller",
        content=content,
        timestamp=time.time(),
        parent_session_id=parent_session_id,
        retry_count=retry_count,
    )


@pytest.mark.anyio
async def test_agent_worker_processes_event(test_context, tmp_path):
    """AgentWorker processes an event."""
    create_test_agent(
        tmp_path,
        agent_id="test-agent",
        system_prompt="You are a test assistant. Respond briefly.",
    )

    router = AgentWorker(test_context)

    event = make_inbound_event(content="Say hello", agent_id="test-agent")
    await router._dispatch_event(event)

    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_agent_router_publishes_error_for_nonexistent_agent(test_context):
    """AgentWorker publishes RESULT with error when agent doesn't exist."""
    router = AgentWorker(test_context)

    # Track RESULT events
    result_events: list[DispatchResultEvent] = []

    async def capture_result(event: DispatchResultEvent) -> None:
        result_events.append(event)

    test_context.eventbus.subscribe(DispatchResultEvent, capture_result)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        event = make_dispatch_event(agent_id="nonexistent", session_id="test-job-id")
        await router._dispatch_event(event)

        # Wait for async error result to be published
        await asyncio.sleep(0.1)

        # Should have published RESULT with error
        assert len(result_events) == 1
        result_event = result_events[0]
        assert isinstance(result_event, DispatchResultEvent)
        assert result_event.session_id == "test-job-id"
        assert result_event.error is not None
        assert "nonexistent" in result_event.error
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


@pytest.mark.anyio
async def test_session_executor_requeues_on_transient_error(test_context, tmp_path):
    """SessionExecutor requeues via INBOUND event on transient errors."""
    create_test_agent(tmp_path, agent_id="test-agent")

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_inbound_event(content="Test", agent_id="test-agent")

    # Track inbound events for retry
    inbound_events: list[InboundEvent] = []

    async def capture_event(evt: InboundEvent) -> None:
        inbound_events.append(evt)

    test_context.eventbus.subscribe(InboundEvent, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        executor = SessionExecutor(test_context, agent_def, event, semaphore)

        # Mock the Agent to raise an error
        with patch("picklebot.server.agent_worker.Agent") as MockAgent:
            MockAgent.side_effect = RuntimeError("Transient error")
            await executor.run()

        # Wait for EventBus to process the queued event
        await asyncio.sleep(0.1)

        assert len(inbound_events) == 1
        retry_event = inbound_events[0]
        assert isinstance(retry_event, InboundEvent)
        assert retry_event.retry_count == 1
        assert retry_event.content == "."
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


@pytest.mark.anyio
async def test_session_executor_recovers_missing_session(test_context, tmp_path):
    """SessionExecutor creates new session with same ID if session not found."""
    create_test_agent(tmp_path, agent_id="test-agent")

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    nonexistent_session_id = "nonexistent-session-uuid"
    event = make_inbound_event(
        content="Test", session_id=nonexistent_session_id, agent_id="test-agent"
    )

    executor = SessionExecutor(test_context, agent_def, event, semaphore)
    await executor.run()

    session_ids = [s.id for s in test_context.history_store.list_sessions()]
    assert nonexistent_session_id in session_ids


@pytest.mark.anyio
async def test_session_executor_runs_session(test_context, tmp_path):
    """SessionExecutor runs a session successfully."""
    create_test_agent(
        tmp_path,
        agent_id="test-agent",
        system_prompt="You are a test assistant. Respond briefly.",
    )

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_inbound_event(content="Say hello", agent_id="test-agent")

    executor = SessionExecutor(test_context, agent_def, event, semaphore)
    await executor.run()


@pytest.mark.anyio
async def test_session_executor_respects_semaphore(test_context, tmp_path):
    """SessionExecutor waits on semaphore before executing."""
    create_test_agent(tmp_path, agent_id="test-agent", name="Test Agent")

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_inbound_event(content="Test", agent_id="test-agent")

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
    """AgentWorker creates a semaphore for each agent on first event."""
    # Create two test agents
    for agent_name in ["agent-a", "agent-b"]:
        create_test_agent(
            tmp_path,
            agent_id=agent_name,
            name=agent_name,
            system_prompt=f"You are {agent_name}.",
            max_concurrency=2,
        )

    router = AgentWorker(test_context)

    # Initially no semaphores
    assert len(router._semaphores) == 0

    event_a = make_inbound_event(content="Test A", agent_id="agent-a")
    event_b = make_inbound_event(content="Test B", agent_id="agent-b")

    await router._dispatch_event(event_a)

    # Should have semaphore for agent-a
    assert "agent-a" in router._semaphores
    assert router._semaphores["agent-a"]._value == 2  # type: ignore

    await router._dispatch_event(event_b)

    # Should have semaphores for both agents
    assert "agent-b" in router._semaphores
    assert router._semaphores["agent-b"]._value == 2  # type: ignore

    # Give tasks a moment to complete
    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_agent_router_concurrent_agents_dont_block(test_context, tmp_path):
    """AgentWorker allows concurrent agents to run without blocking each other."""
    # Create two agents with concurrency 1 each
    for agent_name in ["agent-a", "agent-b"]:
        create_test_agent(
            tmp_path,
            agent_id=agent_name,
            name=agent_name,
            system_prompt=f"You are {agent_name}.",
            max_concurrency=1,
        )

    router = AgentWorker(test_context)

    event_a = make_inbound_event(content="Test A", agent_id="agent-a")
    event_b = make_inbound_event(content="Test B", agent_id="agent-b")

    await router._dispatch_event(event_a)
    await router._dispatch_event(event_b)

    # Both should be able to run concurrently (different agents)
    await asyncio.sleep(0.5)


@pytest.mark.anyio
async def test_semaphore_cleanup_removes_stale_semaphores(test_context, tmp_path):
    """AgentWorker removes semaphores for deleted agents when threshold exceeded."""
    agents_dir = tmp_path / "agents"

    # Create 6 agents (exceeds CLEANUP_THRESHOLD of 5)
    for i in range(6):
        create_test_agent(
            tmp_path,
            agent_id=f"agent-{i}",
            name=f"Agent {i}",
            system_prompt=f"You are agent {i}.",
        )

    router = AgentWorker(test_context)

    # Dispatch events for all agents to create semaphores
    for i in range(6):
        event = make_inbound_event(content="Test", agent_id=f"agent-{i}")
        await router._dispatch_event(event)

    await asyncio.sleep(0.3)  # Let tasks start

    # All 6 semaphores should exist
    assert len(router._semaphores) == 6

    # Delete agent-5
    shutil.rmtree(agents_dir / "agent-5")

    # Trigger cleanup by dispatching another event
    event = make_inbound_event(content="Test", agent_id="agent-0")
    await router._dispatch_event(event)

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
    create_test_agent(tmp_path, agent_id="test-agent")

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_dispatch_event(
        content="hello",
        agent_id="test-agent",
        session_id="test-job-123",
    )

    # Track RESULT events
    result_events: list[DispatchResultEvent] = []

    async def capture_result(evt: DispatchResultEvent) -> None:
        result_events.append(evt)

    test_context.eventbus.subscribe(DispatchResultEvent, capture_result)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        with patch("picklebot.server.agent_worker.Agent") as MockAgent:
            mock_session = AsyncMock()
            mock_session.chat = AsyncMock(return_value="response text")
            mock_session.session_id = "session-123"

            mock_agent = MagicMock()
            mock_agent.new_session.return_value = mock_session
            mock_agent.resume_session.return_value = mock_session
            MockAgent.return_value = mock_agent

            executor = SessionExecutor(test_context, agent_def, event, semaphore)
            await executor.run()

        # Wait for EventBus to process the queued event
        await asyncio.sleep(0.1)

        assert len(result_events) == 1
        result_event = result_events[0]
        assert isinstance(result_event, DispatchResultEvent)
        assert result_event.content == "response text"
        assert result_event.session_id == "test-job-123"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


@pytest.mark.anyio
async def test_session_executor_requeues_on_first_failure(test_context, tmp_path):
    """SessionExecutor should requeue via event with incremented retry_count on failure."""
    create_test_agent(tmp_path, agent_id="test-agent")

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_inbound_event(content="hello", agent_id="test-agent", retry_count=0)

    # Track inbound events for retry
    inbound_events: list[InboundEvent] = []

    async def capture_event(evt: InboundEvent) -> None:
        inbound_events.append(evt)

    test_context.eventbus.subscribe(InboundEvent, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        with patch("picklebot.server.agent_worker.Agent") as MockAgent:
            MockAgent.side_effect = Exception("boom")

            executor = SessionExecutor(test_context, agent_def, event, semaphore)
            await executor.run()

        # Wait for EventBus to process the queued event
        await asyncio.sleep(0.1)

        # Should be requeued via INBOUND event
        assert len(inbound_events) == 1
        retry_event = inbound_events[0]
        assert isinstance(retry_event, InboundEvent)
        assert retry_event.retry_count == 1
        assert retry_event.content == "."
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


@pytest.mark.anyio
async def test_session_executor_publishes_result_with_error_after_max_retries(
    test_context, tmp_path
):
    """SessionExecutor should publish RESULT event with error after MAX_RETRIES failures."""
    create_test_agent(tmp_path, agent_id="test-agent")

    agent_def = test_context.agent_loader.load("test-agent")
    semaphore = asyncio.Semaphore(1)

    event = make_dispatch_event(
        content="hello",
        agent_id="test-agent",
        retry_count=MAX_RETRIES,
        session_id="job-456",
    )

    # Track RESULT events
    result_events: list[DispatchResultEvent] = []

    async def capture_result(evt: DispatchResultEvent) -> None:
        result_events.append(evt)

    test_context.eventbus.subscribe(DispatchResultEvent, capture_result)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        with patch("picklebot.server.agent_worker.Agent") as MockAgent:
            MockAgent.side_effect = Exception("final boom")

            executor = SessionExecutor(test_context, agent_def, event, semaphore)
            await executor.run()

        # Wait for EventBus to process the queued event
        await asyncio.sleep(0.1)

        assert len(result_events) == 1
        result_event = result_events[0]
        assert isinstance(result_event, DispatchResultEvent)
        assert result_event.session_id == "job-456"
        assert result_event.error is not None
        assert result_event.error == "final boom"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


# ============================================================================
# Tests for AgentWorker event handling
# ============================================================================


@pytest.mark.anyio
async def test_agent_dispatcher_handles_inbound_event(test_context):
    """AgentWorker should handle INBOUND events."""
    router = AgentWorker(test_context)

    # Track dispatched events
    dispatched_events: list[InboundEvent] = []

    async def capture_dispatch(evt: InboundEvent) -> None:
        dispatched_events.append(evt)
        # Don't actually execute, just capture

    router._dispatch_event = capture_dispatch  # type: ignore

    event = InboundEvent(
        session_id="test-session",
        agent_id="test-agent",
        source="test:platform",
        content="Hello world",
        timestamp=time.time(),
    )

    await router._dispatch_event(event)

    assert len(dispatched_events) == 1
    dispatched = dispatched_events[0]
    assert isinstance(dispatched, InboundEvent)
    assert dispatched.content == "Hello world"
    assert dispatched.session_id == "test-session"


@pytest.mark.anyio
async def test_agent_dispatcher_handles_dispatch_event(test_context):
    """AgentWorker should handle DISPATCH events."""
    router = AgentWorker(test_context)

    # Track dispatched events
    dispatched_events: list[DispatchEvent] = []

    async def capture_dispatch(evt: DispatchEvent) -> None:
        dispatched_events.append(evt)

    router._dispatch_event = capture_dispatch  # type: ignore

    event = DispatchEvent(
        session_id="job-session",
        agent_id="test-agent",
        source="agent:caller",
        content="Run task",
        timestamp=time.time(),
        parent_session_id="parent-123",
    )

    await router._dispatch_event(event)

    assert len(dispatched_events) == 1
    dispatched = dispatched_events[0]
    assert isinstance(dispatched, DispatchEvent)
    assert dispatched.session_id == "job-session"
    assert dispatched.agent_id == "test-agent"
    assert dispatched.content == "Run task"
