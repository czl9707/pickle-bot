"""Cron job executor."""

import asyncio
import logging
from datetime import datetime

from croniter import croniter

from picklebot.core.context import SharedContext
from picklebot.core.cron_loader import CronDef, CronMetadata
from picklebot.core.agent import Agent
from picklebot.frontend.base import SilentFrontend

logger = logging.getLogger(__name__)


def find_due_job(
    jobs: list[CronMetadata], now: datetime | None = None
) -> CronMetadata | None:
    """
    Find the first job that's due to run.

    A job is due if the current minute matches its cron schedule.

    Args:
        jobs: List of cron metadata to check
        now: Current time (defaults to datetime.now())

    Returns:
        First due job, or None if none are due
    """
    if not jobs:
        return None

    now = now or datetime.now()
    # Round down to the minute for comparison
    now_minute = now.replace(second=0, microsecond=0)

    for job in jobs:
        try:
            # Use croniter.match() to check if current time matches schedule
            if croniter.match(job.schedule, now_minute):
                return job
        except Exception as e:
            logger.warning(f"Error checking schedule for {job.id}: {e}")
            continue

    return None


class CronExecutor:
    """Executes cron jobs on schedule."""

    def __init__(self, context: SharedContext):
        """
        Initialize CronExecutor.

        Args:
            context: Shared application context
        """
        self.context = context

    async def run(self) -> None:
        """
        Main loop: check every minute, execute due jobs.

        Runs forever until interrupted.
        """
        logger.info("CronExecutor started")

        while True:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"Error in tick: {e}")

            await asyncio.sleep(60)

    async def _tick(self) -> None:
        """Check schedules and run due jobs."""
        jobs = self.context.cron_loader.discover_crons()
        due_job_meta = find_due_job(jobs)

        if due_job_meta:
            logger.info(f"Running cron job: {due_job_meta.id}")
            try:
                cron_def = self.context.cron_loader.load(due_job_meta.id)
                await self._run_job(cron_def)
            except Exception as e:
                logger.error(f"Cron job {due_job_meta.id} failed: {e}")

    async def _run_job(self, cron_def: CronDef) -> None:
        """
        Execute a single cron job.

        Args:
            cron_def: Full cron job definition
        """
        try:
            agent_def = self.context.agent_loader.load(cron_def.agent)
            agent = Agent(agent_def, self.context)

            session = agent.new_session()

            await session.chat(cron_def.prompt, SilentFrontend())

            logger.info(f"Cron job {cron_def.id} completed successfully")
        except Exception as e:
            logger.error(f"Error executing cron job {cron_def.id}: {e}")
            raise
