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


class AgentJobRouter(Worker):
    """Routes jobs to session executors with per-agent concurrency control."""

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext", agent_queue: asyncio.Queue[Job]):
        super().__init__(context)
        self.agent_queue = agent_queue
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def run(self) -> None:
        """Process jobs sequentially, dispatch to executors."""
        self.logger.info("AgentJobRouter started")

        while True:
            job = await self.agent_queue.get()
            self._dispatch_job(job)
            self.agent_queue.task_done()
            self._maybe_cleanup_semaphores()

    def _dispatch_job(self, job: Job) -> None:
        """Create executor task for job."""
        try:
            agent_def = self.context.agent_loader.load(job.agent_id)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {job.agent_id}: {e}")
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(
            SessionExecutor(self.context, agent_def, job, sem, self.agent_queue).run()
        )

    def _get_or_create_semaphore(self, agent_def: "AgentDef") -> asyncio.Semaphore:
        """Get existing or create new semaphore for agent."""
        if agent_def.id not in self._semaphores:
            self._semaphores[agent_def.id] = asyncio.Semaphore(
                agent_def.max_concurrency
            )
            self.logger.debug(
                f"Created semaphore for {agent_def.id} with value {agent_def.max_concurrency}"
            )
        return self._semaphores[agent_def.id]

    def _maybe_cleanup_semaphores(self) -> None:
        """Remove semaphores for deleted agents."""
        if len(self._semaphores) <= self.CLEANUP_THRESHOLD:
            return

        existing = {a.id for a in self.context.agent_loader.discover_agents()}
        stale = set(self._semaphores.keys()) - existing
        for agent_id in stale:
            del self._semaphores[agent_id]
            self.logger.debug(f"Cleaned up semaphore for deleted agent: {agent_id}")


# Keep AgentWorker as an alias for backward compatibility
AgentWorker = AgentJobRouter
