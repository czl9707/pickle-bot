"""Agent worker for executing agent jobs."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from picklebot.server.base import Worker, Job
from picklebot.core.agent import Agent, SessionMode
from picklebot.events.types import Event, EventType, Source
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

            # Set result on pending future if registered
            future = self.context.get_future(self.job.job_id)
            if future and not future.done():
                future.set_result(response)

        except Exception as e:
            self.logger.error(f"Session failed: {e}")

            if self.job.retry_count < MAX_RETRIES:
                self.job.retry_count += 1
                self.job.message = "."
                # Publish retry as INBOUND event (re-queuing work into the system)
                retry_event = Event(
                    type=EventType.INBOUND,
                    session_id=self.job.session_id,
                    content=self.job.message,
                    source=Source.retry(),
                    timestamp=time.time(),
                    metadata={
                        "job_id": self.job.job_id,
                        "agent_id": self.job.agent_id,
                        "mode": self.job.mode.value,
                        "retry_count": self.job.retry_count,
                    },
                )
                await self.context.eventbus.publish(retry_event)
            else:
                # Set exception on pending future
                future = self.context.get_future(self.job.job_id)
                if future and not future.done():
                    future.set_exception(e)


class AgentDispatcherWorker(Worker):
    """Dispatches jobs to session executors with per-agent concurrency control.

    Subscribes to:
    - INBOUND events (from platforms, cron, retries)
    - DISPATCH events (from subagent calls)
    """

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext", default_agent_id: str | None = None):
        super().__init__(context)
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._default_agent_id = default_agent_id or context.config.default_agent

    async def handle_inbound(self, event: Event) -> None:
        """Handle INBOUND event (from platforms, cron, retries)."""
        if event.type != EventType.INBOUND:
            return

        metadata = event.metadata or {}
        job_id = metadata.get("job_id")
        agent_id = metadata.get("agent_id", self._default_agent_id)
        mode_str = metadata.get("mode", "CHAT")
        retry_count = metadata.get("retry_count", 0)

        try:
            mode = SessionMode(mode_str)
        except ValueError:
            mode = SessionMode.CHAT

        # Create job from event
        job = Job(
            job_id=job_id or event.session_id,
            agent_id=agent_id,
            message=event.content,
            mode=mode,
            session_id=event.session_id,
            retry_count=retry_count,
        )

        self._dispatch_job(job)
        self.logger.debug(f"Dispatched job for INBOUND event, job_id={job.job_id}")

    async def handle_dispatch(self, event: Event) -> None:
        """Handle DISPATCH event (from subagent calls)."""
        if event.type != EventType.DISPATCH:
            return

        metadata = event.metadata or {}
        job_id = metadata.get("job_id")
        agent_id = metadata.get("agent_id", self._default_agent_id)
        mode_str = metadata.get("mode", "JOB")

        try:
            mode = SessionMode(mode_str)
        except ValueError:
            mode = SessionMode.JOB

        # Create job from event
        job = Job(
            job_id=job_id or event.session_id,
            agent_id=agent_id,
            message=event.content,
            mode=mode,
            session_id=event.session_id if event.session_id != job_id else None,
            retry_count=metadata.get("retry_count", 0),
        )

        self._dispatch_job(job)
        self.logger.debug(f"Dispatched job for DISPATCH event, job_id={job.job_id}")

    def subscribe(self) -> None:
        """Subscribe to INBOUND and DISPATCH events."""
        self.context.eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
        self.context.eventbus.subscribe(EventType.DISPATCH, self.handle_dispatch)
        self.logger.info(
            "AgentDispatcherWorker subscribed to INBOUND and DISPATCH events"
        )

    def unsubscribe(self) -> None:
        """Unsubscribe from events."""
        self.context.eventbus.unsubscribe(self.handle_inbound)
        self.context.eventbus.unsubscribe(self.handle_dispatch)

    async def run(self) -> None:
        """Keep worker alive (jobs dispatched via event handlers)."""
        self.logger.info("AgentDispatcherWorker started")

        # Just keep the task alive - actual work is done in event handlers
        try:
            while True:
                await asyncio.sleep(60)
                self._maybe_cleanup_semaphores()
        except asyncio.CancelledError:
            raise

    def _dispatch_job(self, job: Job) -> None:
        """Create executor task for job."""
        try:
            agent_def = self.context.agent_loader.load(job.agent_id)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {job.agent_id}: {e}")
            # Set exception on pending future if registered
            future = self.context.get_future(job.job_id)
            if future and not future.done():
                future.set_exception(e)
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
