"""Agent worker for executing agent jobs."""

import asyncio
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Union

from .worker import SubscriberWorker
from picklebot.core.agent import Agent
from picklebot.core.events import (
    AgentEventSource,
    Event,
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

ProcessableEvent = Union[InboundEvent, DispatchEvent]


class AgentWorker(SubscriberWorker):
    """Dispatches events to session executors with per-agent concurrency control.

    Auto-subscribes to:
    - InboundEvent (from platforms, cron, retries)
    - DispatchEvent (from subagent calls)
    """

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self._semaphores: dict[str, asyncio.Semaphore] = {}

        # Auto-subscribe to events
        self.context.eventbus.subscribe(InboundEvent, self.dispatch_event)
        self.context.eventbus.subscribe(DispatchEvent, self.dispatch_event)
        self.logger.info(
            "AgentWorker subscribed to InboundEvent and DispatchEvent events"
        )

    async def dispatch_event(self, event: ProcessableEvent) -> None:
        """Create executor task for typed event."""
        agent_id = event.agent_id

        try:
            agent_def = self.context.agent_loader.load(agent_id)
        except DefNotFoundError as e:
            logger.error(f"Agent not found: {agent_id}: {e}")

            result_event = self.create_reponse_event(
                event,
                agent_id,
                content="",
                error=str(e),
            )
            await self.context.eventbus.publish(result_event)
            return

        asyncio.create_task(self.exec_session(event, agent_def))

    async def exec_session(
        self, event: ProcessableEvent, agent_def: "AgentDef"
    ) -> None:
        sem = self._get_or_create_semaphore(agent_def)
        session_id = event.session_id

        async with sem:
            try:
                agent = Agent(agent_def, self.context)
                if session_id:
                    try:
                        session = agent.resume_session(session_id)
                    except ValueError:
                        logger.warning(f"Session {session_id} not found, creating new")
                        session = agent.new_session(event.source, session_id=session_id)
                else:
                    session = agent.new_session(event.source)
                    session_id = session.session_id

                response = await session.chat(event.content)
                logger.info(f"Session completed: {session_id}")

                result_event = self.create_reponse_event(
                    event,
                    agent_def.id,
                    response,
                )
                await self.context.eventbus.publish(result_event)

            except Exception as e:
                logger.error(f"Session failed: {e}")

                if event.retry_count < MAX_RETRIES:
                    # Use dataclasses.replace() for retry logic
                    retry_event = replace(
                        event,
                        retry_count=event.retry_count + 1,
                        content=".",  # Minimal message for retry
                    )
                    await self.context.eventbus.publish(retry_event)
                else:
                    result_event = self.create_reponse_event(
                        event,
                        agent_def.id,
                        content="",
                        error=str(e),
                    )
                    await self.context.eventbus.publish(result_event)

        self._maybe_cleanup_semaphores(agent_def)

    def create_reponse_event(
        self,
        event: ProcessableEvent,
        agent_id: str,
        content: str,
        error: str | None = None,
    ) -> Event:
        if isinstance(event, DispatchEvent):
            return DispatchResultEvent(
                session_id=event.session_id,
                agent_id=agent_id,
                source=AgentEventSource(agent_id),
                content=content,
                error=str(error) if error else None,
            )
        else:
            return OutboundEvent(
                session_id=event.session_id,
                agent_id=agent_id,
                source=AgentEventSource(agent_id),
                content=content,
                error=str(error) if error else None,
            )

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

    def _maybe_cleanup_semaphores(self, agent_def: "AgentDef") -> None:
        """Remove semaphores for certain agents."""
        if agent_def.id not in self._semaphores:
            return

        if not self._semaphores[agent_def.id]._waiters:
            del self._semaphores[agent_def.id]
