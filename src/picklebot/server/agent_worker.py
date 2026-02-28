"""Agent worker for executing agent jobs."""

import asyncio
import logging
from typing import TYPE_CHECKING

from picklebot.server.base import Worker, Job
from picklebot.core.agent import Agent, SessionMode
from picklebot.events.types import Event, EventType
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef


# Maximum number of retry attempts for failed sessions
MAX_RETRIES = 3


class SessionExecutor:
    """Executes a single agent session job."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        job: Job,
        semaphore: asyncio.Semaphore,
    ):
        self.context = context
        self.agent_def = agent_def
        self.job = job
        self.semaphore = semaphore
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

            response = await session.chat(self.job.message)
            self.logger.info(f"Session completed: {session.session_id}")

            self.job.result_future.set_result(response)

        except Exception as e:
            self.logger.error(f"Session failed: {e}")

            if self.job.retry_count < MAX_RETRIES:
                self.job.retry_count += 1
                self.job.message = "."
                await self.context.agent_queue.put(self.job)
            else:
                self.job.result_future.set_exception(e)


class AgentDispatcherWorker(Worker):
    """Dispatches jobs to session executors with per-agent concurrency control.

    Subscribes to INBOUND events and also processes jobs from the queue
    (for subagent dispatch and retries).
    """

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext", default_agent_id: str | None = None):
        super().__init__(context)
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._default_agent_id = default_agent_id or context.config.default_agent

    async def handle_inbound(self, event: Event) -> None:
        """Handle INBOUND event by creating and dispatching a Job."""
        if event.type != EventType.INBOUND:
            return

        # Create job from event
        job = Job(
            session_id=event.session_id,
            agent_id=self._default_agent_id,
            message=event.content,
            mode=SessionMode.CHAT,
        )
        job.result_future = asyncio.get_event_loop().create_future()

        self._dispatch_job(job)
        self.logger.debug(f"Dispatched job for INBOUND event, session={event.session_id}")

    def subscribe(self) -> None:
        """Subscribe to INBOUND events."""
        self.context.eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
        self.logger.info("AgentDispatcherWorker subscribed to INBOUND events")

    def unsubscribe(self) -> None:
        """Unsubscribe from INBOUND events."""
        self.context.eventbus.unsubscribe(self.handle_inbound)

    async def run(self) -> None:
        """Process jobs from queue (subagent dispatch, retries)."""
        self.logger.info("AgentDispatcherWorker started")

        while True:
            job = await self.context.agent_queue.get()
            self._dispatch_job(job)
            self.context.agent_queue.task_done()
            self._maybe_cleanup_semaphores()

    def _dispatch_job(self, job: Job) -> None:
        """Create executor task for job."""
        try:
            agent_def = self.context.agent_loader.load(job.agent_id)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {job.agent_id}: {e}")
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(SessionExecutor(self.context, agent_def, job, sem).run())

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
AgentWorker = AgentDispatcherWorker
