"""Cron worker for scheduled job dispatch."""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from croniter import croniter

from picklebot.server.base import Worker, Job
from picklebot.core.agent import SessionMode
from picklebot.frontend.base import SilentFrontend

if TYPE_CHECKING:
    from picklebot.core.cron_loader import CronDef
    from picklebot.core.context import SharedContext


def find_due_jobs(
    jobs: list["CronDef"], now: datetime | None = None
) -> list["CronDef"]:
    """
    Find all jobs that are due to run.

    A job is due if the current minute matches its cron schedule.

    Args:
        jobs: List of cron definitions to check
        now: Current time (defaults to datetime.now())

    Returns:
        List of due jobs (may be empty)
    """
    if not jobs:
        return []

    now = now or datetime.now()
    now_minute = now.replace(second=0, microsecond=0)

    due_jobs = []
    for job in jobs:
        try:
            if croniter.match(job.schedule, now_minute):
                due_jobs.append(job)
        except Exception as e:
            logging.warning(f"Error checking schedule for {job.id}: {e}")
            continue

    return due_jobs


class CronWorker(Worker):
    """Finds due cron jobs, dispatches to agent queue."""

    def __init__(self, context: "SharedContext", agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue

    async def run(self) -> None:
        """Check every minute for due jobs."""
        self.logger.info("CronWorker started")

        while True:
            try:
                await self._tick()
            except Exception as e:
                self.logger.error(f"Error in tick: {e}")

            await asyncio.sleep(60)

    async def _tick(self) -> None:
        """Find and dispatch due jobs."""
        jobs = self.context.cron_loader.discover_crons()
        due_jobs = find_due_jobs(jobs)

        for cron_def in due_jobs:
            job = Job(
                session_id=None,  # Always new session
                agent_id=cron_def.agent,
                message=cron_def.prompt,
                frontend=SilentFrontend(),
                mode=SessionMode.JOB,
            )
            await self.agent_queue.put(job)
            self.logger.info(f"Dispatched cron job: {cron_def.id}")
