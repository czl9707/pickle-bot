"""Tests for CronWorker."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import patch

from picklebot.server.cron_worker import CronWorker, find_due_jobs
from picklebot.server.base import Job
from picklebot.core.cron_loader import CronDef
from picklebot.core.agent import SessionMode


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


@pytest.mark.anyio
async def test_cron_worker_dispatches_due_job(test_context):
    """CronWorker dispatches due jobs to the queue."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = CronWorker(test_context, queue)

    # Create a mock cron job that is due
    mock_cron = CronDef(
        id="test-cron",
        name="Test Cron",
        agent="pickle",
        schedule="*/5 * * * *",  # Every 5 minutes
        prompt="Test prompt from cron",
    )

    # Mock discover_crons to return our known cron job
    with patch.object(
        test_context.cron_loader, "discover_crons", return_value=[mock_cron]
    ):
        # Patch find_due_jobs to return our mock (ensures it's considered due)
        with patch(
            "picklebot.server.cron_worker.find_due_jobs", return_value=[mock_cron]
        ):
            await worker._tick()

    # Verify job was dispatched to queue
    assert not queue.empty()
    job = queue.get_nowait()
    assert job.session_id is None
    assert job.agent_id == "pickle"
    assert job.message == "Test prompt from cron"
    assert job.mode == SessionMode.JOB


@pytest.mark.anyio
async def test_cron_worker_deletes_one_off_after_dispatch(test_context):
    """CronWorker deletes one-off crons after dispatching to queue."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = CronWorker(test_context, queue)

    # Create a one-off cron job
    mock_cron = CronDef(
        id="one-off-cron",
        name="One Off Cron",
        agent="pickle",
        schedule="*/5 * * * *",
        prompt="One off task",
        one_off=True,
    )

    with patch.object(
        test_context.cron_loader, "discover_crons", return_value=[mock_cron]
    ):
        with patch(
            "picklebot.server.cron_worker.find_due_jobs", return_value=[mock_cron]
        ):
            with patch("picklebot.server.cron_worker.shutil.rmtree") as mock_rmtree:
                await worker._tick()

    # Verify job was dispatched
    assert not queue.empty()
    job = queue.get_nowait()
    assert job.message == "One off task"

    # Verify one-off cron was deleted
    expected_path = test_context.cron_loader.config.crons_path / "one-off-cron"
    mock_rmtree.assert_called_once_with(expected_path)


@pytest.mark.anyio
async def test_cron_worker_keeps_recurring_cron(test_context):
    """CronWorker does not delete recurring crons."""
    queue: asyncio.Queue[Job] = asyncio.Queue()
    worker = CronWorker(test_context, queue)

    # Create a recurring cron job (one_off=False is default)
    mock_cron = CronDef(
        id="recurring-cron",
        name="Recurring Cron",
        agent="pickle",
        schedule="*/5 * * * *",
        prompt="Recurring task",
    )

    with patch.object(
        test_context.cron_loader, "discover_crons", return_value=[mock_cron]
    ):
        with patch(
            "picklebot.server.cron_worker.find_due_jobs", return_value=[mock_cron]
        ):
            with patch("picklebot.server.cron_worker.shutil.rmtree") as mock_rmtree:
                await worker._tick()

    # Verify job was dispatched
    assert not queue.empty()

    # Verify cron was NOT deleted
    mock_rmtree.assert_not_called()
