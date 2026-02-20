"""Tests for CronExecutor."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from datetime import datetime

from picklebot.core.cron_executor import find_due_jobs, CronExecutor
from picklebot.core.cron_loader import CronDef


class TestFindDueJobs:
    """Test the find_due_jobs helper."""

    def test_returns_empty_list_when_no_jobs(self):
        """Return empty list when job list is empty."""
        result = find_due_jobs([])
        assert result == []

    def test_returns_all_due_jobs(self):
        """Return all jobs that are due."""
        # Use a specific time where we know */5 should be due (minute 10)
        now = datetime(2026, 2, 15, 10, 10, 0)  # 10:10:00 - divisible by 5

        # Create jobs with different schedules
        # Job that runs every 5 minutes (due at minute 10)
        due_job = CronDef(
            id="due-job",
            name="Due Job",
            agent="pickle",
            schedule="*/5 * * * *",
            prompt="Test prompt",
        )
        # Job that runs at midnight (not due at 10:10)
        not_due_job = CronDef(
            id="not-due",
            name="Not Due",
            agent="pickle",
            schedule="0 0 * * *",
            prompt="Test prompt",
        )

        jobs = [due_job, not_due_job]
        result = find_due_jobs(jobs, now)

        # Only the */5 job should be due
        assert len(result) == 1
        assert result[0].id == "due-job"

    def test_returns_empty_list_when_no_jobs_due(self):
        """Return empty list when no jobs are due."""
        # Use a time that definitely won't match the rare schedule
        # (minute 10 of hour 10 on day 15 of February)
        now = datetime(2026, 2, 15, 10, 10, 0)

        # Create a job that only runs at a very specific time
        # (minute 59 of hour 23 on day 31 of December)
        job = CronDef(
            id="rare-job",
            name="Rare Job",
            agent="pickle",
            schedule="59 23 31 12 *",
            prompt="Test prompt",
        )

        result = find_due_jobs([job], now)
        # This job should not be due at 10:10 on Feb 15
        assert result == []


class TestCronExecutorOneOff:
    """Test one-off cron deletion."""

    @pytest.fixture
    def temp_crons_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.anyio
    async def test_deletes_one_off_cron_after_success(self, temp_crons_dir):
        """One-off cron folder is deleted after successful execution."""
        # Create a one-off cron file
        cron_dir = temp_crons_dir / "one-off-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: One Off\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "one_off: true\n"
            "---\n"
            "Do once."
        )

        # Mock the context
        context = MagicMock()
        context.cron_loader.config.crons_path = temp_crons_dir

        # Mock agent loading and session
        mock_agent_def = MagicMock()
        context.agent_loader.load.return_value = mock_agent_def

        with patch("picklebot.core.cron_executor.Agent") as MockAgent:
            mock_agent = MagicMock()
            mock_session = AsyncMock()
            mock_session.chat = AsyncMock()
            mock_agent.new_session.return_value = mock_session
            MockAgent.return_value = mock_agent

            executor = CronExecutor(context)
            cron_def = CronDef(
                id="one-off-job",
                name="One Off",
                agent="pickle",
                schedule="*/5 * * * *",
                prompt="Do once.",
                one_off=True,
            )

            await executor._run_job(cron_def)

        # Verify cron folder was deleted
        assert not cron_dir.exists()

    @pytest.mark.anyio
    async def test_keeps_one_off_cron_on_failure(self, temp_crons_dir):
        """One-off cron folder is kept if execution fails."""
        # Create a one-off cron file
        cron_dir = temp_crons_dir / "failing-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Failing\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "one_off: true\n"
            "---\n"
            "Fail."
        )

        # Mock the context
        context = MagicMock()
        context.cron_loader.config.crons_path = temp_crons_dir

        # Mock agent loading to raise an error
        context.agent_loader.load.side_effect = Exception("Agent not found")

        executor = CronExecutor(context)
        cron_def = CronDef(
            id="failing-job",
            name="Failing",
            agent="pickle",
            schedule="*/5 * * * *",
            prompt="Fail.",
            one_off=True,
        )

        with pytest.raises(Exception, match="Agent not found"):
            await executor._run_job(cron_def)

        # Verify cron folder still exists
        assert cron_dir.exists()

    @pytest.mark.anyio
    async def test_keeps_recurring_cron_after_success(self, temp_crons_dir):
        """Recurring cron (one_off=False) is not deleted after success."""
        # Create a recurring cron file
        cron_dir = temp_crons_dir / "recurring-job"
        cron_dir.mkdir()
        (cron_dir / "CRON.md").write_text(
            "---\n"
            "name: Recurring\n"
            "agent: pickle\n"
            "schedule: '*/5 * * * *'\n"
            "---\n"
            "Do repeatedly."
        )

        # Mock the context
        context = MagicMock()
        context.cron_loader.config.crons_path = temp_crons_dir

        # Mock agent loading and session
        mock_agent_def = MagicMock()
        context.agent_loader.load.return_value = mock_agent_def

        with patch("picklebot.core.cron_executor.Agent") as MockAgent:
            mock_agent = MagicMock()
            mock_session = AsyncMock()
            mock_session.chat = AsyncMock()
            mock_agent.new_session.return_value = mock_session
            MockAgent.return_value = mock_agent

            executor = CronExecutor(context)
            cron_def = CronDef(
                id="recurring-job",
                name="Recurring",
                agent="pickle",
                schedule="*/5 * * * *",
                prompt="Do repeatedly.",
                one_off=False,
            )

            await executor._run_job(cron_def)

        # Verify cron folder still exists
        assert cron_dir.exists()
