"""Agent worker for executing agent jobs."""

import asyncio
import logging
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Union

from .worker import SubscriberWorker
from picklebot.core.agent import Agent, SessionMode
from picklebot.core.events import (
    Event,
    EventType,
    Source,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
)
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef


# Maximum number of retry attempts for failed sessions
MAX_RETRIES = 3

logger = logging.getLogger(__name__)

# Type alias for events that can be processed by SessionExecutor
ProcessableEvent = Union[InboundEvent, DispatchEvent]


class SessionExecutor:
    """Executes a single agent session from a typed event."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        event: ProcessableEvent,
        semaphore: asyncio.Semaphore,
    ):
        self.context = context
        self.agent_def = agent_def
        self.event = event
        self.semaphore = semaphore

        # Extract fields from typed event
        self.agent_id = event.agent_id
        self.retry_count = event.retry_count
        # DispatchEvent always uses JOB mode, InboundEvent uses CHAT mode
        self.mode = (
            SessionMode.JOB if isinstance(event, DispatchEvent) else SessionMode.CHAT
        )

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
                    logger.warning(f"Session {session_id} not found, creating new")
                    session = agent.new_session(self.mode, session_id=session_id)
            else:
                session = agent.new_session(self.mode)
                session_id = session.session_id

            response = await session.chat(self.event.content)
            logger.info(f"Session completed: {session_id}")

            # Publish result event based on input type
            if isinstance(self.event, DispatchEvent):
                result_event = DispatchResultEvent(
                    session_id=session_id,
                    agent_id=self.agent_def.id,
                    source=Source.agent(self.agent_def.id),
                    content=response,
                    timestamp=time.time(),
                )
            else:
                result_event = OutboundEvent(
                    session_id=session_id,
                    agent_id=self.agent_def.id,
                    source=Source.agent(self.agent_def.id),
                    content=response,
                    timestamp=time.time(),
                )
            await self.context.eventbus.publish(result_event)

        except Exception as e:
            logger.error(f"Session failed: {e}")

            if self.retry_count < MAX_RETRIES:
                # Use dataclasses.replace() for retry logic
                retry_event = replace(
                    self.event,
                    retry_count=self.retry_count + 1,
                    content=".",  # Minimal message for retry
                )
                await self.context.eventbus.publish(retry_event)
            else:
                # Publish result event with error based on input type
                if isinstance(self.event, DispatchEvent):
                    result_event = DispatchResultEvent(
                        session_id=session_id,
                        agent_id=self.agent_def.id,
                        source=Source.agent(self.agent_def.id),
                        content="",
                        timestamp=time.time(),
                        error=str(e),
                    )
                else:
                    result_event = OutboundEvent(
                        session_id=session_id,
                        agent_id=self.agent_def.id,
                        source=Source.agent(self.agent_def.id),
                        content="",
                        timestamp=time.time(),
                        error=str(e),
                    )
                await self.context.eventbus.publish(result_event)


class AgentWorker(SubscriberWorker):
    """Dispatches events to session executors with per-agent concurrency control.

    Auto-subscribes to:
    - INBOUND events (from platforms, cron, retries)
    - DISPATCH events (from subagent calls)
    """

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self._semaphores: dict[str, asyncio.Semaphore] = {}

        # Auto-subscribe to events
        self.context.eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
        self.context.eventbus.subscribe(EventType.DISPATCH, self.handle_dispatch)
        self.logger.info("AgentWorker subscribed to INBOUND and DISPATCH events")

    async def handle_inbound(self, event: Event) -> None:
        """Handle INBOUND event (from platforms, cron, retries)."""
        # Type-check: only process InboundEvent instances
        if not isinstance(event, InboundEvent):
            return

        await self._dispatch_event(event)
        logger.debug(f"Dispatched job for INBOUND event, session_id={event.session_id}")

    async def handle_dispatch(self, event: Event) -> None:
        """Handle DISPATCH event (from subagent calls)."""
        # Type-check: only process DispatchEvent instances
        if not isinstance(event, DispatchEvent):
            return

        await self._dispatch_event(event)
        logger.debug(
            f"Dispatched job for DISPATCH event, session_id={event.session_id}"
        )

    async def _dispatch_event(self, event: ProcessableEvent) -> None:
        """Create executor task for typed event."""
        agent_id = event.agent_id

        try:
            agent_def = self.context.agent_loader.load(agent_id)
        except DefNotFoundError as e:
            logger.error(f"Agent not found: {agent_id}: {e}")

            # Publish result event with error based on input type
            if isinstance(event, DispatchEvent):
                result_event = DispatchResultEvent(
                    session_id=event.session_id,
                    agent_id=agent_id,
                    source="agent:dispatcher",
                    content="",
                    timestamp=time.time(),
                    error=str(e),
                )
            else:
                result_event = OutboundEvent(
                    session_id=event.session_id,
                    agent_id=agent_id,
                    source="agent:dispatcher",
                    content="",
                    timestamp=time.time(),
                    error=str(e),
                )
            await self.context.eventbus.publish(result_event)
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(SessionExecutor(self.context, agent_def, event, sem).run())
        self._maybe_cleanup_semaphores()

    def _get_or_create_semaphore(self, agent_def: "AgentDef") -> asyncio.Semaphore:
        """Get existing or create new semaphore for agent."""
        if agent_def.id not in self._semaphores:
            self._semaphores[agent_def.id] = asyncio.Semaphore(
                agent_def.max_concurrency
            )
            logger.debug(
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
            logger.debug(f"Cleaned up semaphore for deleted agent: {agent_id}")
