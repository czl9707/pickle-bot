"""Central event bus for pub/sub event distribution."""

import asyncio
import json
import logging
import os
from collections import defaultdict
from typing import Awaitable, Callable, TYPE_CHECKING

from picklebot.server.worker import Worker

from .events import (
    Event,
    EventType,
    deserialize_event,
)

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]


class EventBus(Worker):
    """Central event bus with subscription support and async dispatch.

    Uses internal queue to decouple publish and dispatch.
    Runs recovery on startup. Processes events from queue in run().
    """

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.context = context
        self._subscribers: dict[EventType, list[Handler]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self.pending_dir = context.config.event_path / "pending"
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        """Subscribe a handler to an event type."""
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type.value} events")

    def unsubscribe(self, handler: Handler) -> None:
        """Remove a handler from all subscriptions."""
        for event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Unsubscribed handler from {event_type.value} events")

    async def publish(self, event: Event) -> None:
        """Publish an event to the internal queue (non-blocking)."""
        await self._queue.put(event)
        logger.debug(f"Queued {event.type.value} event from {event.source}")

    async def run(self) -> None:
        """Process events from queue, starting with recovery."""
        logger.info("EventBus started")

        # Run recovery first
        await self._recover()

        # Process events from queue
        try:
            while True:
                event = await self._queue.get()
                try:
                    await self._dispatch(event)
                except Exception as e:
                    logger.error(f"Error dispatching event: {e}")
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            logger.info("EventBus stopping...")
            raise

    async def _dispatch(self, event: Event) -> None:
        """Persist if OUTBOUND, then notify subscribers."""
        await self._persist_outbound(event)
        await self._notify_subscribers(event)
        logger.debug(f"Dispatched {event.type.value} event from {event.source}")

    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers of an event (waits for all handlers to complete)."""
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return

        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in event handler: {result}")

    async def _persist_outbound(self, event: Event) -> None:
        """Persist event to disk (only OUTBOUND events)."""
        if event.type != EventType.OUTBOUND:
            return

        filename = f"{event.timestamp}_{event.session_id}.json"
        final_path = self.pending_dir / filename
        tmp_path = self.pending_dir / f".tmp.{os.getpid()}.{filename}"

        data = json.dumps(event.to_dict(), ensure_ascii=False)

        # Atomic write: tmp + fsync + rename
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(str(tmp_path), str(final_path))
        logger.debug(f"Persisted event to {final_path}")

    async def _recover(self) -> int:
        """Recover pending events from previous crash. Returns count recovered."""
        pending_files = list(self.pending_dir.glob("*.json"))
        if not pending_files:
            return 0

        logger.info(f"Recovering {len(pending_files)} pending events")
        count = 0

        for file_path in pending_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Use deserialize_event to handle typed events
                event = deserialize_event(data)
                await self._notify_subscribers(event)
                count += 1
                logger.debug(f"Recovered event from {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to recover {file_path}: {e}")

        logger.info(f"Recovered {count} events")
        return count

    def ack(self, event: Event) -> None:
        """Acknowledge successful delivery, delete persisted event."""
        filename = f"{event.timestamp}_{event.session_id}.json"
        final_path = self.pending_dir / filename
        if final_path.exists():
            final_path.unlink()
            logger.debug(f"Acked and deleted {filename}")
