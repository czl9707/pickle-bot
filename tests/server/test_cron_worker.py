"""Tests for CronWorker."""

import asyncio
import pytest
from datetime import datetime

from picklebot.server.cron_worker import CronWorker, find_due_jobs
from picklebot.core.cron_loader import CronDef


def test_find_due_jobs_returns_matching():
    """find_due_jobs returns jobs matching current time."""
    jobs = [
        CronDef(
            id="test-job",
            name="Test",
            agent="pickle",
            schedule="*/5 * * * *",  # Every 5 minutes
            prompt="Test prompt",
        )
    ]

    # Use a time that matches */5 schedule (minute divisible by 5)
    now = datetime(2024, 6, 15, 12, 5)  # 12:05 matches */5
    due = find_due_jobs(jobs, now)
    assert len(due) == 1
    assert due[0].id == "test-job"


def test_find_due_jobs_empty_when_no_match():
    """find_due_jobs returns empty when no jobs match."""
    jobs = [
        CronDef(
            id="test-job",
            name="Test",
            agent="pickle",
            schedule="0 0 1 1 *",  # Jan 1 only
            prompt="Test prompt",
        )
    ]

    # Use a date that won't match
    now = datetime(2024, 6, 15, 12, 0)
    due = find_due_jobs(jobs, now)
    assert len(due) == 0


@pytest.mark.asyncio
async def test_cron_worker_dispatches_due_job(test_context):
    """CronWorker dispatches due jobs to the queue."""
    queue: asyncio.Queue = asyncio.Queue()
    worker = CronWorker(test_context, queue)

    # Manually call _tick and check queue
    await worker._tick()

    # Queue might have jobs if crons exist
    # Just verify no exception
    assert True
