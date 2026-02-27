# src/picklebot/events/bus.py
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Callable, Awaitable
from collections import defaultdict

from .types import Event, EventType

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]

class EventBus:
    """Central event bus with subscription support."""

    def __init__(self, events_dir: Path | None = None):
        self._subscribers: dict[EventType, list[Handler]] = defaultdict(list)
        self.events_dir = events_dir or Path.home() / ".events"
        self.pending_dir = self.events_dir / "pending"
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
        """Publish an event: persist if OUTBOUND, then notify subscribers."""

        await self._persist_inbound(event)
        await self._notify_subscribers(event)

        logger.debug(f"Published {event.type.value} event from {event.source}")

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

    async def _persist_inbound(self, event: Event) -> None:
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

    async def recover(self) -> int:
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
                event = Event.from_dict(data)
                await self._notify_subscribers(event)
                count += 1
                logger.debug(f"Recovered event from {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to recover {file_path}: {e}")

        logger.info(f"Recovered {count} events")
        return count

    def ack(self, filename: str) -> None:
        """Acknowledge successful delivery, delete persisted event."""
        file_path = self.pending_dir / filename
        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Acked and deleted {filename}")
