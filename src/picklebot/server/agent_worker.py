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
            agent_def = self.context.agent_loader.load(job.agent_id)
            agent = Agent(agent_def, self.context)

            if job.session_id:
                try:
                    session = agent.resume_session(job.session_id)
                except ValueError:
                    # Session not found in history - create new with same ID
                    self.logger.warning(f"Session {job.session_id} not found, creating new")
                    session = agent.new_session(job.mode, session_id=job.session_id)
            else:
                session = agent.new_session(job.mode)
                job.session_id = session.session_id

            await session.chat(job.message, job.frontend)

            self.logger.info(f"Job completed: session={job.session_id}")

        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {job.agent_id}: {e}")
        except Exception as e:
            self.logger.error(f"Job failed: {e}")

            job.message = "."
            await self.agent_queue.put(job)
