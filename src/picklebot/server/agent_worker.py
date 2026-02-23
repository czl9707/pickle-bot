"""Agent worker for executing agent jobs."""

import asyncio
import logging
from typing import TYPE_CHECKING

from picklebot.server.base import Worker, Job
from picklebot.core.agent import Agent
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef


class SessionExecutor:
    """Executes a single agent session job."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        job: Job,
        semaphore: asyncio.Semaphore,
        agent_queue: asyncio.Queue[Job],
    ):
        self.context = context
        self.agent_def = agent_def
        self.job = job
        self.semaphore = semaphore
        self.agent_queue = agent_queue
        self.logger = logging.getLogger(
            f"picklebot.server.SessionExecutor.{agent_def.id}"
        )

    async def run(self) -> None:
        """Wait for semaphore, execute session, release."""
        async with self.semaphore:
            await self._execute()

    async def _execute(self) -> None:
        """Run the actual agent session."""
        try:
            agent = Agent(self.agent_def, self.context)

            if self.job.session_id:
                try:
                    session = agent.resume_session(self.job.session_id)
                except ValueError:
                    self.logger.warning(
                        f"Session {self.job.session_id} not found, creating new"
                    )
                    session = agent.new_session(
                        self.job.mode, session_id=self.job.session_id
                    )
            else:
                session = agent.new_session(self.job.mode)
                self.job.session_id = session.session_id

            await session.chat(self.job.message, self.job.frontend)
            self.logger.info(f"Session completed: {session.session_id}")

        except DefNotFoundError:
            self.logger.warning(f"Agent {self.agent_def.id} no longer exists")
        except Exception as e:
            self.logger.error(f"Session failed: {e}")
            self.job.message = "."
            await self.agent_queue.put(self.job)


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
                    self.logger.warning(
                        f"Session {job.session_id} not found, creating new"
                    )
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
