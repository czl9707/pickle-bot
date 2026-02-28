"""Base worker lifecycle management."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class Worker(ABC):
    """Base class for all workers with lifecycle management."""

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
