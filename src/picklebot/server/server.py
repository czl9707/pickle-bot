"""Server orchestrator for worker-based architecture."""

import asyncio
import logging
from typing import TYPE_CHECKING

from picklebot.server.base import Job, Worker
from picklebot.server.agent_worker import AgentWorker
from picklebot.server.cron_worker import CronWorker
from picklebot.server.messagebus_worker import MessageBusWorker

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class Server:
    """Orchestrates workers with queue-based communication."""

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.agent_queue: asyncio.Queue[Job] = asyncio.Queue()
        self.workers: list[Worker] = []

    async def run(self) -> None:
        """Start all workers and monitor for crashes."""
        self._setup_workers()
        self._start_workers()

        try:
            await self._monitor_workers()
        except asyncio.CancelledError:
            logger.info("Server shutting down...")
            await self._stop_all()
            raise

    def _setup_workers(self) -> None:
        """Create all workers."""
        self.workers.append(AgentWorker(self.context, self.agent_queue))
        self.workers.append(CronWorker(self.context, self.agent_queue))

        if self.context.config.messagebus.enabled:
            buses = self.context.messagebus_buses
            if buses:
                self.workers.append(MessageBusWorker(self.context, self.agent_queue))
                logger.info(f"MessageBus enabled with {len(buses)} bus(es)")
            else:
                logger.warning("MessageBus enabled but no buses configured")

    def _start_workers(self) -> None:
        """Start all workers as tasks."""
        for worker in self.workers:
            worker.start()
            logger.info(f"Started {worker.__class__.__name__}")

    async def _monitor_workers(self) -> None:
        """Monitor worker tasks, restart on crash."""
        while True:
            for worker in self.workers:
                if worker.has_crashed():
                    exc = worker.get_exception()
                    if exc is None:
                        logger.warning(
                            f"{worker.__class__.__name__} exited unexpectedly"
                        )
                    else:
                        logger.error(f"{worker.__class__.__name__} crashed: {exc}")

                    worker.start()
                    logger.info(f"Restarted {worker.__class__.__name__}")

            await asyncio.sleep(5)

    async def _stop_all(self) -> None:
        """Stop all workers gracefully."""
        for worker in self.workers:
            await worker.stop()
