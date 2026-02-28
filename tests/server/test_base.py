"""Tests for server base classes."""

from picklebot.server.base import Job
from picklebot.core.agent import SessionMode


class TestJobFields:
    """Tests for Job dataclass fields and defaults."""

    def test_job_defaults(self):
        """Job should have retry_count=0 and auto-generated job_id by default."""
        job = Job(
            agent_id="test",
            message="hello",
            mode=SessionMode.CHAT,
        )
        assert job.session_id is None
        assert job.retry_count == 0
        assert job.job_id is not None  # Auto-generated UUID
