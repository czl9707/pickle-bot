# Event-Driven Messaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace frontend/reply/post mechanism with unified event-driven architecture using EventBus with write-ahead persistence.

**Architecture:** Central EventBus receives all events, persists OutboundMessage to disk before notifying subscribers. DeliveryWorker subscribes to OutboundMessage, handles chunking and platform delivery. Frontend abstraction removed entirely.

**Tech Stack:** Python asyncio, dataclasses, filesystem persistence (tmp+fsync+replace pattern from claw0)

---

## Phase 1: Core Event Infrastructure

### Task 1: Create Event Types

**Files:**
- Create: `src/picklebot/events/__init__.py`
- Create: `src/picklebot/events/types.py`
- Create: `tests/events/test_types.py`

**Step 1: Write the failing test**

```python
# tests/events/test_types.py
import pytest
from picklebot.events.types import Event, EventType


def test_event_creation():
    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello world",
        source="agent:pickle",
        timestamp=12345.0,
        metadata={"agent_id": "pickle"},
    )
    assert event.type == EventType.OUTBOUND
    assert event.session_id == "test-session"
    assert event.content == "Hello world"
    assert event.source == "agent:pickle"
    assert event.timestamp == 12345.0
    assert event.metadata == {"agent_id": "pickle"}


def test_event_default_metadata():
    event = Event(
        type=EventType.INBOUND,
        session_id="test-session",
        content="Hi",
        source="telegram:user_123",
        timestamp=12345.0,
    )
    assert event.metadata == {}


def test_event_to_dict():
    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
        metadata={"key": "value"},
    )
    result = event.to_dict()
    assert result == {
        "type": "outbound",
        "session_id": "test-session",
        "content": "Hello",
        "source": "agent:pickle",
        "timestamp": 12345.0,
        "metadata": {"key": "value"},
    }


def test_event_from_dict():
    data = {
        "type": "outbound",
        "session_id": "test-session",
        "content": "Hello",
        "source": "agent:pickle",
        "timestamp": 12345.0,
        "metadata": {"key": "value"},
    }
    event = Event.from_dict(data)
    assert event.type == EventType.OUTBOUND
    assert event.session_id == "test-session"
    assert event.content == "Hello"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_types.py -v`
Expected: FAIL with module import errors

**Step 3: Create the events module structure**

```python
# src/picklebot/events/__init__.py
from .types import Event, EventType

__all__ = ["Event", "EventType"]
```

```python
# src/picklebot/events/types.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of events in the system."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    STATUS = "status"


@dataclass
class Event:
    """Platform-agnostic event."""

    type: EventType
    session_id: str
    content: str
    source: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "content": self.content,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize event from dictionary."""
        return cls(
            type=EventType(data["type"]),
            session_id=data["session_id"],
            content=data["content"],
            source=data["source"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_types.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/ tests/events/
git commit -m "feat(events): add Event and EventType dataclasses"
```

---

### Task 2: Create EventBus with Subscription

**Files:**
- Create: `src/picklebot/events/bus.py`
- Create: `tests/events/test_bus.py`

**Step 1: Write the failing test**

```python
# tests/events/test_bus.py
import asyncio
import pytest
from picklebot.events.bus import EventBus
from picklebot.events.types import Event, EventType


@pytest.fixture
def event_bus():
    return EventBus()


def test_event_bus_creation(event_bus):
    assert event_bus is not None
    assert event_bus._subscribers == {}


@pytest.mark.asyncio
async def test_subscribe_and_notify(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.OUTBOUND, handler)

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus._notify_subscribers(event)

    assert len(received) == 1
    assert received[0] == event


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus):
    received_1 = []
    received_2 = []

    async def handler_1(event: Event):
        received_1.append(event)

    async def handler_2(event: Event):
        received_2.append(event)

    event_bus.subscribe(EventType.OUTBOUND, handler_1)
    event_bus.subscribe(EventType.OUTBOUND, handler_2)

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus._notify_subscribers(event)

    assert len(received_1) == 1
    assert len(received_2) == 1


@pytest.mark.asyncio
async def test_unsubscribe(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.OUTBOUND, handler)
    event_bus.unsubscribe(handler)

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus._notify_subscribers(event)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_subscribe_to_multiple_types(event_bus):
    received_outbound = []
    received_inbound = []

    async def outbound_handler(event: Event):
        received_outbound.append(event)

    async def inbound_handler(event: Event):
        received_inbound.append(event)

    event_bus.subscribe(EventType.OUTBOUND, outbound_handler)
    event_bus.subscribe(EventType.INBOUND, inbound_handler)

    outbound_event = Event(
        type=EventType.OUTBOUND,
        session_id="test",
        content="Out",
        source="agent",
        timestamp=1.0,
    )
    inbound_event = Event(
        type=EventType.INBOUND,
        session_id="test",
        content="In",
        source="user",
        timestamp=2.0,
    )

    await event_bus._notify_subscribers(outbound_event)
    await event_bus._notify_subscribers(inbound_event)

    assert len(received_outbound) == 1
    assert len(received_inbound) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_bus.py -v`
Expected: FAIL with module import errors

**Step 3: Write minimal implementation**

```python
# src/picklebot/events/bus.py
import asyncio
import logging
from typing import Callable, Awaitable
from collections import defaultdict

from .types import Event, EventType

logger = logging.getLogger(__name__)

Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Central event bus with subscription support."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Handler]] = defaultdict(list)

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

    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers of an event (does not wait for completion)."""
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return

        # Fire all handlers concurrently, don't wait
        for handler in handlers:
            try:
                asyncio.create_task(handler(event))
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_bus.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/bus.py tests/events/test_bus.py
git commit -m "feat(events): add EventBus with subscription support"
```

---

### Task 3: Add Persistence to EventBus

**Files:**
- Modify: `src/picklebot/events/bus.py`
- Create: `tests/events/test_bus_persistence.py`

**Step 1: Write the failing test**

```python
# tests/events/test_bus_persistence.py
import json
import os
import pytest
import tempfile
from pathlib import Path
from picklebot.events.bus import EventBus
from picklebot.events.types import Event, EventType


@pytest.fixture
def temp_events_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def event_bus(temp_events_dir):
    return EventBus(events_dir=temp_events_dir)


def test_event_bus_has_persistence_dir(event_bus, temp_events_dir):
    assert event_bus.events_dir == temp_events_dir
    assert event_bus.pending_dir == temp_events_dir / "pending"
    assert event_bus.failed_dir == temp_events_dir / "failed"


@pytest.mark.asyncio
async def test_persist_outbound_event(event_bus, temp_events_dir):
    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus._persist(event)

    # Check file was created
    pending_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 1

    # Verify content
    with open(pending_files[0]) as f:
        data = json.load(f)
    assert data["session_id"] == "test-session"
    assert data["content"] == "Hello"


@pytest.mark.asyncio
async def test_persist_skips_non_outbound(event_bus, temp_events_dir):
    inbound_event = Event(
        type=EventType.INBOUND,
        session_id="test-session",
        content="Hi",
        source="telegram:user",
        timestamp=12345.0,
    )
    status_event = Event(
        type=EventType.STATUS,
        session_id="test-session",
        content="Working...",
        source="agent",
        timestamp=12345.0,
    )

    await event_bus._persist(inbound_event)
    await event_bus._persist(status_event)

    # No files should be created
    pending_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 0


@pytest.mark.asyncio
async def test_ack_deletes_persisted_event(event_bus, temp_events_dir):
    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus._persist(event)

    # Get the filename
    pending_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 1
    filename = pending_files[0].name

    # Ack the event
    event_bus.ack(filename)

    # File should be deleted
    pending_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 0


@pytest.mark.asyncio
async def test_atomic_write(event_bus, temp_events_dir):
    """Test that files are written atomically (tmp + fsync + rename)."""
    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus._persist(event)

    # No temp files should remain
    tmp_files = list((temp_events_dir / "pending").glob(".tmp.*"))
    assert len(tmp_files) == 0

    # Only final file should exist
    json_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(json_files) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_bus_persistence.py -v`
Expected: FAIL with attribute errors

**Step 3: Add persistence to EventBus**

```python
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
    """Central event bus with subscription and persistence support."""

    def __init__(self, events_dir: Path | None = None):
        self._subscribers: dict[EventType, list[Handler]] = defaultdict(list)
        self.events_dir = events_dir or Path.home() / ".events"
        self.pending_dir = self.events_dir / "pending"
        self.failed_dir = self.events_dir / "failed"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure persistence directories exist."""
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

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

    async def _persist(self, event: Event) -> None:
        """Persist event to disk (only OUTBOUND events)."""
        if event.type != EventType.OUTBOUND:
            return

        filename = f"{event.timestamp}_{event.session_id}.json"
        final_path = self.pending_dir / filename
        tmp_path = self.pending_dir / f".tmp.{os.getpid()}.{filename}"

        data = json.dumps(event.to_dict(), indent=2, ensure_ascii=False)

        # Atomic write: tmp + fsync + rename
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(str(tmp_path), str(final_path))
        logger.debug(f"Persisted event to {final_path}")

    def ack(self, filename: str) -> None:
        """Acknowledge successful delivery, delete persisted event."""
        file_path = self.pending_dir / filename
        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Acked and deleted {filename}")

    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers of an event (does not wait for completion)."""
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                asyncio.create_task(handler(event))
            except Exception as e:
                logger.error(f"Error creating event handler task: {e}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_bus_persistence.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/bus.py tests/events/test_bus_persistence.py
git commit -m "feat(events): add write-ahead persistence to EventBus"
```

---

### Task 4: Add Publish Method to EventBus

**Files:**
- Modify: `src/picklebot/events/bus.py`
- Modify: `tests/events/test_bus_persistence.py`

**Step 1: Write the failing test**

```python
# Add to tests/events/test_bus_persistence.py

@pytest.mark.asyncio
async def test_publish_outbound_persists_and_notifies(event_bus, temp_events_dir):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.OUTBOUND, handler)

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await event_bus.publish(event)

    # Allow async tasks to complete
    await asyncio.sleep(0.1)

    # Should have persisted
    pending_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 1

    # Should have notified subscriber
    assert len(received) == 1


@pytest.mark.asyncio
async def test_publish_inbound_no_persist(event_bus, temp_events_dir):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.INBOUND, handler)

    event = Event(
        type=EventType.INBOUND,
        session_id="test-session",
        content="Hi",
        source="telegram:user",
        timestamp=12345.0,
    )

    await event_bus.publish(event)

    await asyncio.sleep(0.1)

    # Should NOT have persisted
    pending_files = list((temp_events_dir / "pending").glob("*.json"))
    assert len(pending_files) == 0

    # Should have notified subscriber
    assert len(received) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_bus_persistence.py -v`
Expected: FAIL with attribute error (no publish method)

**Step 3: Add publish method**

```python
# Add to src/picklebot/events/bus.py

    async def publish(self, event: Event) -> None:
        """Publish an event: persist if OUTBOUND, then notify subscribers."""
        # Persist first (blocking, for OUTBOUND only)
        await self._persist(event)

        # Then notify subscribers (non-blocking)
        await self._notify_subscribers(event)

        logger.debug(f"Published {event.type.value} event from {event.source}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_bus_persistence.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/bus.py tests/events/test_bus_persistence.py
git commit -m "feat(events): add publish method to EventBus"
```

---

### Task 5: Add Recovery to EventBus

**Files:**
- Modify: `src/picklebot/events/bus.py`
- Create: `tests/events/test_bus_recovery.py`

**Step 1: Write the failing test**

```python
# tests/events/test_bus_recovery.py
import json
import pytest
import tempfile
from pathlib import Path
from picklebot.events.bus import EventBus
from picklebot.events.types import Event, EventType


@pytest.fixture
def temp_events_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_recover_republishes_pending_events(temp_events_dir):
    # Create a pending event file manually
    pending_dir = temp_events_dir / "pending"
    pending_dir.mkdir(parents=True)

    event_data = {
        "type": "outbound",
        "session_id": "test-session",
        "content": "Hello",
        "source": "agent:pickle",
        "timestamp": 12345.0,
        "metadata": {},
    }

    with open(pending_dir / "12345.0_test-session.json", "w") as f:
        json.dump(event_data, f)

    # Create bus and track received events
    received = []

    async def handler(event: Event):
        received.append(event)

    bus = EventBus(events_dir=temp_events_dir)
    bus.subscribe(EventType.OUTBOUND, handler)

    # Recover
    await bus.recover()

    # Allow async tasks
    import asyncio
    await asyncio.sleep(0.1)

    # Event should have been republished
    assert len(received) == 1
    assert received[0].session_id == "test-session"


@pytest.mark.asyncio
async def test_recover_empty_pending_dir(temp_events_dir):
    bus = EventBus(events_dir=temp_events_dir)

    received = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.OUTBOUND, handler)

    await bus.recover()

    import asyncio
    await asyncio.sleep(0.1)

    assert len(received) == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_bus_recovery.py -v`
Expected: FAIL with attribute error (no recover method)

**Step 3: Add recovery method**

```python
# Add to src/picklebot/events/bus.py

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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_bus_recovery.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/bus.py tests/events/test_bus_recovery.py
git commit -m "feat(events): add recovery method to EventBus"
```

---

## Phase 2: DeliveryWorker

### Task 6: Create DeliveryWorker with Chunking

**Files:**
- Create: `src/picklebot/events/delivery.py`
- Create: `tests/events/test_delivery.py`

**Step 1: Write the failing test**

```python
# tests/events/test_delivery.py
import pytest
from picklebot.events.delivery import chunk_message


def test_chunk_message_under_limit():
    result = chunk_message("Hello world", limit=100)
    assert result == ["Hello world"]


def test_chunk_message_exact_limit():
    message = "x" * 100
    result = chunk_message(message, limit=100)
    assert result == [message]


def test_chunk_message_splits_at_paragraph():
    message = "Para one\n\nPara two\n\nPara three"
    result = chunk_message(message, limit=15)
    # "Para one" = 8 chars
    # "Para two" = 8 chars
    # "Para three" = 10 chars
    assert len(result) == 3
    assert "Para one" in result[0]
    assert "Para two" in result[1]


def test_chunk_message_hard_split():
    message = "A" * 50  # Single long "paragraph"
    result = chunk_message(message, limit=20)
    assert len(result) == 3
    assert len(result[0]) == 20
    assert len(result[1]) == 20
    assert len(result[2]) == 10


def test_chunk_message_mixed():
    message = "Short\n\n" + "B" * 50 + "\n\nEnd"
    result = chunk_message(message, limit=20)
    # "Short" = 5 chars - chunk 1
    # 50 B's - chunks 2,3,4 (20+20+10)
    # "End" = 3 chars - chunk 5
    assert len(result) >= 3


def test_platform_limits():
    from picklebot.events.delivery import PLATFORM_LIMITS

    assert PLATFORM_LIMITS["telegram"] == 4096
    assert PLATFORM_LIMITS["discord"] == 2000
    assert PLATFORM_LIMITS["cli"] == float("inf")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_delivery.py -v`
Expected: FAIL with module import errors

**Step 3: Write chunking implementation**

```python
# src/picklebot/events/delivery.py
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Platform message size limits
PLATFORM_LIMITS: dict[str, float] = {
    "telegram": 4096,
    "discord": 2000,
    "cli": float("inf"),  # no limit
}


def chunk_message(content: str, limit: int) -> list[str]:
    """Split message at paragraph boundaries, respecting limit.

    Args:
        content: The message to chunk
        limit: Maximum characters per chunk

    Returns:
        List of message chunks
    """
    if len(content) <= limit:
        return [content]

    chunks = []
    paragraphs = content.split("\n\n")
    current = ""

    for para in paragraphs:
        # Try to add to current chunk
        if current:
            potential = current + "\n\n" + para
        else:
            potential = para

        if len(potential) <= limit:
            current = potential
        else:
            # Current chunk is complete
            if current:
                chunks.append(current)

            # Handle paragraph that exceeds limit
            if len(para) > limit:
                # Hard split
                for i in range(0, len(para), limit):
                    chunks.append(para[i : i + limit])
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_delivery.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/delivery.py tests/events/test_delivery.py
git commit -m "feat(events): add message chunking for platform limits"
```

---

### Task 7: Create DeliveryWorker Class

**Files:**
- Modify: `src/picklebot/events/delivery.py`
- Modify: `tests/events/test_delivery.py`

**Step 1: Write the failing test**

```python
# Add to tests/events/test_delivery.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from picklebot.events.delivery import DeliveryWorker
from picklebot.events.types import Event, EventType
from picklebot.events.bus import EventBus


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.config = MagicMock()
    context.eventbus = EventBus()
    # Mock platform buses
    context.telegram_bus = AsyncMock()
    context.discord_bus = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_delivery_worker_creation(mock_context):
    worker = DeliveryWorker(mock_context)
    assert worker.context == mock_context


@pytest.mark.asyncio
async def test_delivery_worker_handles_outbound_event(mock_context):
    worker = DeliveryWorker(mock_context)

    # Mock the lookup
    worker._lookup_platform = MagicMock(return_value={
        "platform": "telegram",
        "chat_id": "123456",
    })

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await worker.handle_event(event)

    # Should have called telegram bus send
    mock_context.telegram_bus.send.assert_called_once_with("123456", "Hello")


@pytest.mark.asyncio
async def test_delivery_worker_handles_cli_platform(mock_context, capsys):
    worker = DeliveryWorker(mock_context)

    # Mock the lookup for CLI
    worker._lookup_platform = MagicMock(return_value={
        "platform": "cli",
    })

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test-session",
        content="Hello CLI",
        source="agent:pickle",
        timestamp=12345.0,
    )

    await worker.handle_event(event)

    # Should print to stdout
    captured = capsys.readouterr()
    assert "Hello CLI" in captured.out
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_delivery.py -v`
Expected: FAIL with import/class errors

**Step 3: Write DeliveryWorker implementation**

```python
# Add to src/picklebot/events/delivery.py

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class DeliveryWorker:
    """Worker that delivers outbound messages to platforms."""

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.logger = logging.getLogger("picklebot.events.DeliveryWorker")

    async def handle_event(self, event: Event) -> None:
        """Handle an outbound message event."""
        if event.type != EventType.OUTBOUND:
            return

        try:
            # Look up where to deliver
            platform_info = self._lookup_platform(event.session_id)
            platform = platform_info["platform"]

            # Get limit and chunk
            limit = int(PLATFORM_LIMITS.get(platform, float("inf")))
            chunks = chunk_message(event.content, limit)

            # Deliver each chunk
            for chunk in chunks:
                await self._deliver(platform, platform_info, chunk)

            # Ack the event
            filename = f"{event.timestamp}_{event.session_id}.json"
            self.context.eventbus.ack(filename)

            self.logger.info(f"Delivered message to {platform} for session {event.session_id}")

        except Exception as e:
            self.logger.error(f"Failed to deliver message: {e}")
            # TODO: Retry logic with backoff

    def _lookup_platform(self, session_id: str) -> dict[str, Any]:
        """Look up platform and delivery context for a session.

        This does the hard work of figuring out where a session lives.
        For now, checks runtime config and messagebus sessions.
        """
        # Check runtime config for session -> platform mapping
        # This is a temporary solution until session management is revamped
        runtime_config = self.context.config.runtime

        # Look in messagebus config for session
        if "messagebus" in runtime_config:
            for platform in ["telegram", "discord"]:
                platform_config = runtime_config.get("messagebus", {}).get(platform, {})
                sessions = platform_config.get("sessions", {})
                for user_id, sess_id in sessions.items():
                    if sess_id == session_id:
                        delivery_context = {}
                        if platform == "telegram":
                            delivery_context["chat_id"] = platform_config.get("default_chat_id", "")
                        elif platform == "discord":
                            delivery_context["channel_id"] = platform_config.get("default_chat_id", "")
                        return {
                            "platform": platform,
                            **delivery_context,
                        }

        # Default to CLI if not found
        return {"platform": "cli"}

    async def _deliver(self, platform: str, platform_info: dict[str, Any], content: str) -> None:
        """Deliver a message chunk to a platform."""
        if platform == "telegram":
            chat_id = platform_info.get("chat_id")
            if chat_id and hasattr(self.context, "telegram_bus"):
                await self.context.telegram_bus.send(chat_id, content)
        elif platform == "discord":
            channel_id = platform_info.get("channel_id")
            if channel_id and hasattr(self.context, "discord_bus"):
                await self.context.discord_bus.send(channel_id, content)
        elif platform == "cli":
            # CLI just prints to stdout
            print(content)

    def subscribe(self, eventbus: EventBus) -> None:
        """Subscribe this worker to an event bus."""
        eventbus.subscribe(EventType.OUTBOUND, self.handle_event)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_delivery.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/delivery.py tests/events/test_delivery.py
git commit -m "feat(events): add DeliveryWorker class"
```

---

### Task 8: Add Retry Logic to DeliveryWorker

**Files:**
- Modify: `src/picklebot/events/delivery.py`
- Create: `tests/events/test_retry.py`

**Step 1: Write the failing test**

```python
# tests/events/test_retry.py
import pytest
from picklebot.events.delivery import compute_backoff_ms, BACKOFF_MS, MAX_RETRIES


def test_backoff_first_retry():
    result = compute_backoff_ms(1)
    # First backoff should be around 5000ms with 20% jitter
    assert 4000 <= result <= 6000


def test_backoff_second_retry():
    result = compute_backoff_ms(2)
    # Second backoff should be around 25000ms with 20% jitter
    assert 20000 <= result <= 30000


def test_backoff_max():
    result = compute_backoff_ms(10)
    # Should cap at last backoff value
    assert 480000 <= result <= 720000  # 600000 +/- 20%


def test_backoff_zero():
    result = compute_backoff_ms(0)
    assert result == 0


def test_constants():
    assert BACKOFF_MS == [5000, 25000, 120000, 600000]
    assert MAX_RETRIES == 5
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_retry.py -v`
Expected: FAIL with import errors

**Step 3: Add retry logic**

```python
# Add to src/picklebot/events/delivery.py

import random
import time

# Retry configuration
BACKOFF_MS = [5000, 25000, 120000, 600000]  # 5s, 25s, 2min, 10min
MAX_RETRIES = 5


def compute_backoff_ms(retry_count: int) -> int:
    """Compute backoff time with jitter.

    Args:
        retry_count: Current retry attempt (1-indexed)

    Returns:
        Backoff time in milliseconds
    """
    if retry_count <= 0:
        return 0

    # Cap at last backoff value
    idx = min(retry_count - 1, len(BACKOFF_MS) - 1)
    base = BACKOFF_MS[idx]

    # Add +/- 20% jitter
    jitter = random.randint(-base // 5, base // 5)
    return max(0, base + jitter)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_retry.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/events/delivery.py tests/events/test_retry.py
git commit -m "feat(events): add retry backoff logic"
```

---

## Phase 3: Integration

### Task 9: Add EventBus to SharedContext

**Files:**
- Modify: `src/picklebot/core/context.py`
- Create: `tests/core/test_context_eventbus.py`

**Step 1: Write the failing test**

```python
# tests/core/test_context_eventbus.py
import pytest
from pathlib import Path
from picklebot.core.context import SharedContext
from picklebot.events.bus import EventBus


def test_shared_context_has_eventbus():
    context = SharedContext.create()
    assert hasattr(context, "eventbus")
    assert isinstance(context.eventbus, EventBus)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_context_eventbus.py -v`
Expected: FAIL with attribute error

**Step 3: Add eventbus to SharedContext**

```python
# Modify src/picklebot/core/context.py
# Add import at top:
from picklebot.events.bus import EventBus

# Add to SharedContext.__init__ or create method:
# self.eventbus = EventBus()
```

(Exact modification depends on current context.py structure - adjust accordingly)

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_context_eventbus.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/context.py tests/core/test_context_eventbus.py
git commit -m "feat(context): add EventBus to SharedContext"
```

---

### Task 10: Create WebSocketWorker Stub

**Files:**
- Create: `src/picklebot/events/websocket.py`
- Create: `tests/events/test_websocket_stub.py`

**Step 1: Create stub implementation**

```python
# src/picklebot/events/websocket.py
"""WebSocket worker for broadcasting events to connected clients.

This is a stub implementation. Future work:
- Accept WebSocket connections
- Maintain set of connected clients
- Subscribe to ALL event types (INBOUND, OUTBOUND, STATUS)
- Broadcast events as JSON to all connected clients
- Handle client connect/disconnect
"""

import logging
from typing import TYPE_CHECKING

from .types import Event, EventType
from .bus import EventBus

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class WebSocketWorker:
    """Stub worker for WebSocket event broadcasting.

    Future implementation:
    - Subscribe to all event types
    - Broadcast to connected WebSocket clients
    - No persistence needed (real-time only)
    """

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.logger = logging.getLogger("picklebot.events.WebSocketWorker")
        self._clients: set = set()  # Future: set of WebSocket connections

    async def handle_event(self, event: Event) -> None:
        """Handle an event by broadcasting to WebSocket clients.

        TODO: Implement actual WebSocket broadcasting.
        For now, just logs the event.
        """
        self.logger.debug(f"WebSocket stub received {event.type.value} event")

    def subscribe(self, eventbus: EventBus) -> None:
        """Subscribe to all event types."""
        eventbus.subscribe(EventType.INBOUND, self.handle_event)
        eventbus.subscribe(EventType.OUTBOUND, self.handle_event)
        eventbus.subscribe(EventType.STATUS, self.handle_event)
        self.logger.info("WebSocketWorker subscribed to all event types")
```

**Step 2: Write simple test**

```python
# tests/events/test_websocket_stub.py
import pytest
from unittest.mock import MagicMock
from picklebot.events.websocket import WebSocketWorker
from picklebot.events.types import Event, EventType
from picklebot.events.bus import EventBus


@pytest.fixture
def mock_context():
    return MagicMock()


def test_websocket_worker_creation(mock_context):
    worker = WebSocketWorker(mock_context)
    assert worker.context == mock_context


@pytest.mark.asyncio
async def test_websocket_worker_handles_event(mock_context):
    worker = WebSocketWorker(mock_context)

    event = Event(
        type=EventType.OUTBOUND,
        session_id="test",
        content="Hello",
        source="agent",
        timestamp=1.0,
    )

    # Should not raise
    await worker.handle_event(event)


def test_websocket_worker_subscribes_to_all_types(mock_context):
    worker = WebSocketWorker(mock_context)
    bus = EventBus()

    worker.subscribe(bus)

    # Check subscriptions exist
    assert len(bus._subscribers[EventType.INBOUND]) == 1
    assert len(bus._subscribers[EventType.OUTBOUND]) == 1
    assert len(bus._subscribers[EventType.STATUS]) == 1
```

**Step 3: Run test to verify it passes**

Run: `uv run pytest tests/events/test_websocket_stub.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/picklebot/events/websocket.py tests/events/test_websocket_stub.py
git commit -m "feat(events): add WebSocketWorker stub"
```

---

## Phase 4: Replace Output Paths

### Task 11: Update Agent to Publish OutboundMessage

**Files:**
- Modify: `src/picklebot/core/agent.py` or `src/picklebot/core/session.py`
- Create: `tests/core/test_agent_events.py`

**Step 1: Write failing test**

```python
# tests/core/test_agent_events.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from picklebot.events.types import Event, EventType


@pytest.mark.asyncio
async def test_agent_publishes_outbound_message():
    # Setup mock context with eventbus
    from picklebot.events.bus import EventBus

    bus = EventBus()
    received = []

    async def capture(event):
        received.append(event)

    bus.subscribe(EventType.OUTBOUND, capture)

    # This test will need adjustment based on actual agent/session API
    # The key assertion: when agent responds, it publishes OUTBOUND event
    pass  # Placeholder - implement based on actual agent structure
```

**Step 2: Modify agent/session to publish events**

Find where `frontend.show_message()` is currently called and replace with:

```python
event = Event(
    type=EventType.OUTBOUND,
    session_id=self.session_id,
    content=response_content,
    source=f"agent:{self.agent_id}",
    timestamp=time.time(),
    metadata={"agent_id": self.agent_id},
)
await self.context.eventbus.publish(event)
```

**Step 3: Run tests**

Run: `uv run pytest tests/core/test_agent_events.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/core/ tests/core/test_agent_events.py
git commit -m "feat(agent): publish OutboundMessage events instead of frontend calls"
```

---

### Task 12: Update post_message_tool

**Files:**
- Modify: `src/picklebot/tools/post_message_tool.py`
- Modify: `tests/tools/test_post_message_tool.py`

**Step 1: Write failing test**

```python
# Add to tests/tools/test_post_message_tool.py

@pytest.mark.asyncio
async def test_post_message_publishes_event():
    from picklebot.events.bus import EventBus
    from picklebot.events.types import EventType

    bus = EventBus()
    received = []

    async def capture(event):
        received.append(event)

    bus.subscribe(EventType.OUTBOUND, capture)

    # Create tool with mock context
    # Call tool
    # Assert event was published
```

**Step 2: Modify post_message_tool**

```python
# Modify src/picklebot/tools/post_message_tool.py
# Replace bus.post() call with:

event = Event(
    type=EventType.OUTBOUND,
    session_id=session_id,  # Need to determine which session
    content=content,
    source="tool:post_message",
    timestamp=time.time(),
)
await context.eventbus.publish(event)
```

**Step 3: Run tests**

Run: `uv run pytest tests/tools/test_post_message_tool.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/tools/post_message_tool.py tests/tools/
git commit -m "feat(tools): post_message_tool publishes events"
```

---

### Task 13: Remove Frontend Folder

**Files:**
- Delete: `src/picklebot/frontend/` (entire folder)
- Modify: Any imports referencing frontend

**Step 1: Find all frontend imports**

Run: `grep -r "from picklebot.frontend" src/`
Run: `grep -r "import.*frontend" src/`

**Step 2: Remove frontend folder**

```bash
rm -rf src/picklebot/frontend/
```

**Step 3: Fix broken imports**

Update any files that imported from frontend to use eventbus instead.

**Step 4: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (may need fixes)

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove Frontend abstraction, replaced by EventBus"
```

---

## Phase 5: Replace Input Paths

### Task 14: Update MessageBusWorker to Publish InboundMessage

**Files:**
- Modify: `src/picklebot/server/messagebus_worker.py`
- Modify: `tests/server/test_messagebus_worker.py`

**Step 1: Write failing test**

**Step 2: Modify MessageBusWorker callback**

Replace direct agent call with event publish:

```python
event = Event(
    type=EventType.INBOUND,
    session_id=session_id,
    content=message,
    source=f"{platform}:{context.user_id}",
    timestamp=time.time(),
    metadata={"chat_id": getattr(context, "chat_id", None)},
)
await self.context.eventbus.publish(event)
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add src/picklebot/server/messagebus_worker.py tests/server/
git commit -m "feat(server): MessageBusWorker publishes InboundMessage events"
```

---

### Task 15: Update CLI to Async Event-Driven

**Files:**
- Modify: `src/picklebot/cli/chat.py`
- Modify: `tests/cli/test_chat.py`

**Step 1: Remove blocking behavior**

- Remove `result_future` wait
- Subscribe CLI to events for its session
- Print output when OutboundMessage received for CLI session

**Step 2: Implement**

```python
# CLI becomes an event subscriber
# When user types message -> publish InboundMessage
# When OutboundMessage for CLI session -> print
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add src/picklebot/cli/ tests/cli/
git commit -m "feat(cli): make CLI async event-driven, remove blocking"
```

---

### Task 16: Wire Agent to Consume InboundMessage Events

**Files:**
- Modify: `src/picklebot/core/agent.py` or `src/picklebot/server/agent_worker.py`

**Step 1: Subscribe agent to InboundMessage**

The agent needs to listen for InboundMessage events and process them:

```python
# In agent initialization or worker setup
eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
```

**Step 2: Implement inbound handler**

```python
async def handle_inbound(self, event: Event) -> None:
    if event.session_id == self.session_id:
        # Process the message
        await self.process_message(event.content)
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add src/picklebot/core/ src/picklebot/server/
git commit -m "feat(agent): consume InboundMessage events from EventBus"
```

---

## Phase 6: Final Integration

### Task 17: Start DeliveryWorker in Server

**Files:**
- Modify: `src/picklebot/server/server.py`

**Step 1: Add DeliveryWorker to server startup**

```python
# In server.py, alongside other workers:
from picklebot.events.delivery import DeliveryWorker

# Create and subscribe
self.delivery_worker = DeliveryWorker(self.context)
self.delivery_worker.subscribe(self.context.eventbus)
```

**Step 2: Run integration test**

**Step 3: Commit**

```bash
git add src/picklebot/server/server.py
git commit -m "feat(server): start DeliveryWorker on server startup"
```

---

### Task 18: Run Full Test Suite and Fix Issues

**Step 1: Run all tests**

Run: `uv run pytest tests/ -v`

**Step 2: Fix any failing tests**

**Step 3: Run linting**

Run: `uv run black . && uv run ruff check .`

**Step 4: Final commit**

```bash
git add -A
git commit -m "fix: resolve integration issues with event-driven messaging"
```

---

## Summary

**Files Created:**
- `src/picklebot/events/__init__.py`
- `src/picklebot/events/types.py`
- `src/picklebot/events/bus.py`
- `src/picklebot/events/delivery.py`
- `src/picklebot/events/websocket.py`
- `tests/events/test_types.py`
- `tests/events/test_bus.py`
- `tests/events/test_bus_persistence.py`
- `tests/events/test_bus_recovery.py`
- `tests/events/test_delivery.py`
- `tests/events/test_retry.py`
- `tests/events/test_websocket_stub.py`
- `tests/core/test_context_eventbus.py`
- `tests/core/test_agent_events.py`

**Files Modified:**
- `src/picklebot/core/context.py`
- `src/picklebot/core/agent.py` or `session.py`
- `src/picklebot/server/server.py`
- `src/picklebot/server/messagebus_worker.py`
- `src/picklebot/tools/post_message_tool.py`
- `src/picklebot/cli/chat.py`

**Files Deleted:**
- `src/picklebot/frontend/` (entire folder)
