"""Agent worker for executing agent jobs."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from picklebot.server.base import Worker
from picklebot.core.agent import Agent, SessionMode
from picklebot.events.types import Event, EventType, Source
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef


# Maximum number of retry attempts for failed sessions
MAX_RETRIES = 3


class SessionExecutor:
    """Executes a single agent session from an event."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        event: Event,
        semaphore: asyncio.Semaphore,
    ):
        self.context = context
        self.agent_def = agent_def
        self.event = event
        self.semaphore = semaphore
        self.logger = logging.getLogger(
            f"picklebot.server.SessionExecutor.{agent_def.id}"
        )

        # Extract fields from event (with defaults)
        metadata = event.metadata or {}
        self.job_id = metadata.get("job_id", event.session_id)
        self.agent_id = metadata.get("agent_id", "")
        self.mode = SessionMode(metadata.get("mode", "CHAT"))
        self.retry_count = metadata.get("retry_count", 0)

    async def run(self) -> None:
        """Wait for semaphore, execute session, release."""
        async with self.semaphore:
            await self._execute()

    async def _execute(self) -> None:
        """Run the actual agent session."""
        session_id = self.event.session_id or None

        try:
            agent = Agent(self.agent_def, self.context)

            if session_id:
                try:
                    session = agent.resume_session(session_id)
                except ValueError:
                    self.logger.warning(f"Session {session_id} not found, creating new")
                    session = agent.new_session(self.mode, session_id=session_id)
            else:
                session = agent.new_session(self.mode)
                session_id = session.session_id

            response = await session.chat(self.event.content)
            self.logger.info(f"Session completed: {session_id}")

            # Publish RESULT event for dispatch callers
            result_event = Event(
                type=EventType.DISPATCH_RESULT,
                session_id=session_id,
                content=response,
                source=Source.agent(self.agent_def.id),
                timestamp=time.time(),
                metadata={"job_id": self.job_id},
            )
            await self.context.eventbus.publish(result_event)

        except Exception as e:
            self.logger.error(f"Session failed: {e}")

            if self.retry_count < MAX_RETRIES:
                # Publish retry as INBOUND event (re-queuing work into the system)
                retry_event = Event(
                    type=EventType.INBOUND,
                    session_id=session_id or "",
                    content=".",  # Minimal message for retry
                    source=Source.retry(),
                    timestamp=time.time(),
                    metadata={
                        "job_id": self.job_id,
                        "agent_id": self.agent_id,
                        "mode": self.mode.value,
                        "retry_count": self.retry_count + 1,
                    },
                )
                await self.context.eventbus.publish(retry_event)
            else:
                # Publish RESULT event with error for dispatch callers
                result_event = Event(
                    type=EventType.DISPATCH_RESULT,
                    session_id=session_id or "",
                    content="",
                    source=Source.agent(self.agent_def.id),
                    timestamp=time.time(),
                    metadata={"job_id": self.job_id, "error": str(e)},
                )
                await self.context.eventbus.publish(result_event)


class AgentDispatcherWorker(Worker):
    """Dispatches events to session executors with per-agent concurrency control.

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

        # Ensure agent_id is set (use default if not in metadata)
        metadata = event.metadata or {}
        if "agent_id" not in metadata:
            # Mutate event to include default agent_id
            event.metadata = {**metadata, "agent_id": self._default_agent_id}

        self._dispatch_event(event)
        self.logger.debug(
            f"Dispatched job for INBOUND event, job_id={metadata.get('job_id')}"
        )

    async def handle_dispatch(self, event: Event) -> None:
        """Handle DISPATCH event (from subagent calls)."""
        if event.type != EventType.DISPATCH:
            return

        self._dispatch_event(event)
        metadata = event.metadata or {}
        self.logger.debug(
            f"Dispatched job for DISPATCH event, job_id={metadata.get('job_id')}"
        )

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

    def _dispatch_event(self, event: Event) -> None:
        """Create executor task for event."""
        metadata = event.metadata or {}
        agent_id = metadata.get("agent_id", self._default_agent_id)

        try:
            agent_def = self.context.agent_loader.load(agent_id)
        except DefNotFoundError as e:
            self.logger.error(f"Agent not found: {agent_id}: {e}")
            # Publish RESULT event with error for dispatch callers
            asyncio.create_task(self._publish_error_result(event, str(e)))
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(SessionExecutor(self.context, agent_def, event, sem).run())

    async def _publish_error_result(self, original_event: Event, error: str) -> None:
        """Publish a RESULT event with error for failed dispatches."""
        metadata = original_event.metadata or {}
        result_event = Event(
            type=EventType.DISPATCH_RESULT,
            session_id=original_event.session_id,
            content="",
            source="agent:dispatcher",
            timestamp=time.time(),
            metadata={
                "job_id": metadata.get("job_id", original_event.session_id),
                "error": error,
            },
        )
        await self.context.eventbus.publish(result_event)

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
