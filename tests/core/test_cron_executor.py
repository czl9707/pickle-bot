"""Tests for CronExecutor."""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from picklebot.core.cron_executor import CronExecutor, find_due_job
from picklebot.core.cron_loader import CronMetadata


class TestFindDueJob:
    """Test the find_due_job helper."""

    def test_returns_none_when_no_jobs(self):
        """Return None when job list is empty."""
        result = find_due_job([])
        assert result is None

    def test_returns_first_due_job(self):
        """Return the first job that's due."""
        # Use a specific time where we know */5 should be due (minute 10)
        now = datetime(2026, 2, 15, 10, 10, 0)  # 10:10:00 - divisible by 5

        # Create jobs with different schedules
        # Job that runs every 5 minutes (due at minute 10)
        due_job = CronMetadata(
            id="due-job",
            name="Due Job",
            agent="pickle",
            schedule="*/5 * * * *",
        )
        # Job that runs at midnight (not due at 10:10)
        not_due_job = CronMetadata(
            id="not-due",
            name="Not Due",
            agent="pickle",
            schedule="0 0 * * *",
        )

        jobs = [due_job, not_due_job]
        result = find_due_job(jobs, now)

        # The */5 job should be due
        assert result is not None
        assert result.id == "due-job"

    def test_returns_none_when_no_jobs_due(self):
        """Return None when no jobs are due."""
        # Use a time that definitely won't match the rare schedule
        # (minute 10 of hour 10 on day 15 of February)
        now = datetime(2026, 2, 15, 10, 10, 0)

        # Create a job that only runs at a very specific time
        # (minute 59 of hour 23 on day 31 of December)
        job = CronMetadata(
            id="rare-job",
            name="Rare Job",
            agent="pickle",
            schedule="59 23 31 12 *",
        )

        result = find_due_job([job], now)
        # This job should not be due at 10:10 on Feb 15
        assert result is None
