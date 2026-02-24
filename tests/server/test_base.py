"""Tests for server base classes."""

from picklebot.server.base import Job
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend


class TestJobFields:
    """Tests for Job dataclass fields and defaults."""

    def test_job_defaults(self):
        """Job should have result_future=None and retry_count=0 by default."""
        job = Job(
            session_id=None,
            agent_id="test",
            message="hello",
            frontend=SilentFrontend(),
            mode=SessionMode.CHAT,
        )
        assert job.result_future is None
        assert job.retry_count == 0
