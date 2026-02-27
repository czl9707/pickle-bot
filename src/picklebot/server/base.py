"""Base classes for worker architecture."""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from picklebot.core.agent import SessionMode

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.frontend.base import Frontend


@dataclass
class Job:
    """A unit of work for the AgentWorker."""

    session_id: str | None  # None = new session, set after first pickup
    agent_id: str  # Which agent to run
    message: str  # User prompt (set to "." after consumed)
    frontend: "Frontend"  # Live frontend object for responses
    mode: SessionMode  # CHAT or JOB
    result_future: asyncio.Future[str]
    retry_count: int = 0


class Worker(ABC):
    """Base class for all workers."""

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.logger = logging.getLogger(f"picklebot.server.{self.__class__.__name__}")
        self._task: asyncio.Task | None = None

    @abstractmethod
    async def run(self) -> None:
        """Main worker loop. Runs until cancelled."""
        pass

    def start(self) -> asyncio.Task:
        """Start the worker as an asyncio Task."""
        self._task = asyncio.create_task(self.run())
        return self._task

    def is_running(self) -> bool:
        """Check if worker is actively running."""
        return self._task is not None and not self._task.done()

    def has_crashed(self) -> bool:
        """Check if worker crashed (done but not cancelled)."""
        return (
            self._task is not None and self._task.done() and not self._task.cancelled()
        )

    def get_exception(self) -> BaseException | None:
        """Get the exception if worker crashed, None otherwise."""
        if self.has_crashed() and self._task is not None:
            return self._task.exception()
        return None

    async def stop(self) -> None:
        """Gracefully stop the worker."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
