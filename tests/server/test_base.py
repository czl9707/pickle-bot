"""Tests for server base classes."""

import asyncio

import pytest

from picklebot.server.base import Job
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend


def test_job_has_result_future():
    """Job should have a result_future field defaulting to None."""
    job = Job(
        session_id=None,
        agent_id="test",
        message="hello",
        frontend=SilentFrontend(),
        mode=SessionMode.CHAT,
    )
    assert hasattr(job, "result_future")
    assert job.result_future is None


@pytest.mark.anyio
async def test_job_result_future_can_be_set():
    """Job's result_future can be set to an asyncio.Future."""
    job = Job(
        session_id=None,
        agent_id="test",
        message="hello",
        frontend=SilentFrontend(),
        mode=SessionMode.CHAT,
    )
    future: asyncio.Future[str] = asyncio.Future()
    job.result_future = future
    assert isinstance(job.result_future, asyncio.Future)


def test_job_has_retry_count():
    """Job should have a retry_count field defaulting to 0."""
    job = Job(
        session_id=None,
        agent_id="test",
        message="hello",
        frontend=SilentFrontend(),
        mode=SessionMode.CHAT,
    )
    assert hasattr(job, "retry_count")
    assert job.retry_count == 0
