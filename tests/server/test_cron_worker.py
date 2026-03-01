"""Tests for CronWorker."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import patch

from picklebot.server.cron_worker import CronWorker, find_due_jobs
from picklebot.core.cron_loader import CronDef
from picklebot.core.events import EventType, InboundEvent


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
async def test_cron_worker_dispatches_due_job(test_context, test_agent_def):
    """CronWorker dispatches due jobs via EventBus as INBOUND events."""
    worker = CronWorker(test_context)

    # Track published events
    published_events: list[InboundEvent] = []

    async def capture_event(event: InboundEvent) -> None:
        published_events.append(event)

    test_context.eventbus.subscribe(EventType.INBOUND, capture_event)

    # Start EventBus worker to process queued events
    eventbus_task = test_context.eventbus.start()

    try:
        # Create a mock cron job that is due
        mock_cron = CronDef(
            id="test-cron",
            name="Test Cron",
            agent="test-agent",
            schedule="*/5 * * * *",  # Every 5 minutes
            prompt="Test prompt from cron",
        )

        # Mock discover_crons and agent_loader
        with patch.object(
            test_context.cron_loader, "discover_crons", return_value=[mock_cron]
        ):
            with patch.object(
                test_context.agent_loader, "load", return_value=test_agent_def
            ):
                with patch(
                    "picklebot.server.cron_worker.find_due_jobs",
                    return_value=[mock_cron],
                ):
                    await worker._tick()

        # Wait for EventBus to process the queued event
        await asyncio.sleep(0.1)

        # Verify event was published as INBOUND
        assert len(published_events) == 1
        event = published_events[0]
        assert event.type == EventType.INBOUND
        assert event.content == "Test prompt from cron"
        # InboundEvent has agent_id directly (not in metadata)
        assert isinstance(event, InboundEvent)
        assert event.agent_id == "test-agent"
    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass


@pytest.mark.anyio
@pytest.mark.parametrize(
    "one_off,should_delete",
    [
        (True, True),
        (False, False),
    ],
)
async def test_one_off_cron_deletion(
    test_context, test_agent_def, one_off, should_delete
):
    """CronWorker deletes one-off crons but keeps recurring crons."""
    worker = CronWorker(test_context)

    mock_cron = CronDef(
        id="test-cron",
        name="Test Cron",
        agent="test-agent",
        schedule="*/5 * * * *",
        prompt="Test task",
        one_off=one_off,
    )

    with patch.object(
        test_context.cron_loader, "discover_crons", return_value=[mock_cron]
    ):
        with patch.object(
            test_context.agent_loader, "load", return_value=test_agent_def
        ):
            with patch(
                "picklebot.server.cron_worker.find_due_jobs", return_value=[mock_cron]
            ):
                with patch("picklebot.server.cron_worker.shutil.rmtree") as mock_rmtree:
                    await worker._tick()

    # Verify deletion behavior
    expected_path = test_context.cron_loader.config.crons_path / "test-cron"
    if should_delete:
        mock_rmtree.assert_called_once_with(expected_path)
    else:
        mock_rmtree.assert_not_called()
