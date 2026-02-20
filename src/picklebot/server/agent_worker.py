"""Agent worker for executing agent jobs."""

import asyncio
from typing import TYPE_CHECKING

from picklebot.server.base import Worker, Job
from picklebot.core.agent import Agent
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class AgentWorker(Worker):
    """Executes agent jobs from the queue."""

    def __init__(self, context: "SharedContext", agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue

    async def run(self) -> None:
        """Process jobs from queue sequentially."""
        self.logger.info("AgentWorker started")

        while True:
            job = await self.agent_queue.get()
            await self._process_job(job)
            self.agent_queue.task_done()

    async def _process_job(self, job: Job) -> None:
        """Execute a single job with crash recovery."""
        try:
            # Load agent
            agent_def = self.context.agent_loader.load(job.agent_id)
            agent = Agent(agent_def, self.context)

            # Get or create session
            if job.session_id:
                session = agent.resume_session(job.session_id)
            else:
                session = agent.new_session(job.mode)
                job.session_id = session.session_id

            # Execute chat
            await session.chat(job.message, job.frontend)

            self.logger.info(f"Job completed: session={job.session_id}")

        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {job.agent_id}: {e}")
            # Don't requeue - agent doesn't exist
        except Exception as e:
            self.logger.error(f"Job failed: {e}")
            # Update job for resume and requeue (for transient errors)
            job.message = "."
            await self.agent_queue.put(job)
