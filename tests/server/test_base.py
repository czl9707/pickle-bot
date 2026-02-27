"""Tests for server base classes."""

import asyncio

import pytest

from picklebot.server.base import Job
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend


class TestJobFields:
    """Tests for Job dataclass fields and defaults."""

    @pytest.mark.asyncio
    async def test_job_defaults(self):
        """Job should have a Future for result_future and retry_count=0 by default."""
        job = Job(
            session_id=None,
            agent_id="test",
            message="hello",
            frontend=SilentFrontend(),
            mode=SessionMode.CHAT,
        )
        assert isinstance(job.result_future, asyncio.Future)
        assert job.retry_count == 0
