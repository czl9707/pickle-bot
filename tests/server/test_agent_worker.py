"""Tests for AgentWorker."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest

from picklebot.server.base import Job
from picklebot.server.agent_worker import AgentWorker
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
