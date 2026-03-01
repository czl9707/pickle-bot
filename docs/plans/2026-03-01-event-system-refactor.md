# Event System Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor events.py to use inheritance, eliminating ~100 lines of duplicated code.

**Architecture:** Single `Event` base class with `to_dict`/`from_dict` methods and auto-timestamp. Four typed event subclasses define only their specific fields plus `type` property. Registry pattern for deserialization.

**Tech Stack:** Python dataclasses, stdlib only

---

### Task 1: Refactor Event Base Class

**Files:**
- Modify: `src/picklebot/core/events.py:94-127`
- Test: `tests/core/test_events.py`

**Step 1: Write the failing tests**

Add tests for the new Event base class behavior:

```python
"""Tests for refactored event system."""

import time
from picklebot.core.events import (
    Event,
    EventType,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    deserialize_event,
)


class TestEventBaseClass:
    """Tests for Event base class."""

    def test_event_has_auto_timestamp(self):
        """Event should auto-populate timestamp."""

        class TestEvent(Event):
            @property
            def type(self) -> EventType:
                return EventType.INBOUND

        before = time.time()
        event = TestEvent(
            session_id="s1",
            agent_id="a1",
            source="test",
            content="hello",
        )
        after = time.time()

        assert before <= event.timestamp <= after

    def test_event_to_dict_includes_type(self):
        """to_dict should include event type."""

        class TestEvent(Event):
            @property
            def type(self) -> EventType:
                return EventType.INBOUND

        event = TestEvent(
            session_id="s1",
            agent_id="a1",
            source="test",
            content="hello",
            timestamp=123.0,
        )

        result = event.to_dict()
        assert result["type"] == "inbound"
        assert result["session_id"] == "s1"
        assert result["timestamp"] == 123.0

    def test_event_from_dict_excludes_type(self):
        """from_dict should work without type in constructor."""

        class TestEvent(Event):
            extra: str = ""

            @property
            def type(self) -> EventType:
                return EventType.INBOUND

        data = {"type": "inbound", "session_id": "s1", "agent_id": "a1",
                "source": "test", "content": "hello", "timestamp": 123.0,
                "extra": "foo"}

        event = TestEvent.from_dict(data)
        assert event.session_id == "s1"
        assert event.extra == "foo"


class TestTypedEvents:
    """Tests for typed event classes."""

    def test_inbound_event_type_property(self):
        """InboundEvent.type should return INBOUND."""
        event = InboundEvent(
            session_id="s1",
            agent_id="a1",
            source="telegram:user1",
            content="hello",
        )
        assert event.type == EventType.INBOUND

    def test_outbound_event_type_property(self):
        """OutboundEvent.type should return OUTBOUND."""
        event = OutboundEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:pickle",
            content="response",
        )
        assert event.type == EventType.OUTBOUND

    def test_dispatch_event_type_property(self):
        """DispatchEvent.type should return DISPATCH."""
        event = DispatchEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:cookie",
            content="task",
            parent_session_id="parent1",
        )
        assert event.type == EventType.DISPATCH

    def test_dispatch_result_event_type_property(self):
        """DispatchResultEvent.type should return DISPATCH_RESULT."""
        event = DispatchResultEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:pickle",
            content="result",
        )
        assert event.type == EventType.DISPATCH_RESULT

    def test_inbound_event_to_dict_roundtrip(self):
        """InboundEvent should serialize/deserialize correctly."""
        original = InboundEvent(
            session_id="s1",
            agent_id="a1",
            source="telegram:user1",
            content="hello",
            timestamp=123.0,
            retry_count=2,
        )
        data = original.to_dict()
        restored = InboundEvent.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.agent_id == original.agent_id
        assert restored.source == original.source
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
        assert restored.retry_count == original.retry_count

    def test_outbound_event_with_error_to_dict_roundtrip(self):
        """OutboundEvent with error should serialize/deserialize correctly."""
        original = OutboundEvent(
            session_id="s1",
            agent_id="a1",
            source="agent:pickle",
            content="response",
            timestamp=123.0,
            error="Something failed",
        )
        data = original.to_dict()
        restored = OutboundEvent.from_dict(data)

        assert restored.error == "Something failed"


class TestDeserializeEvent:
    """Tests for deserialize_event function."""

    def test_deserialize_inbound_event(self):
        """deserialize_event should create correct InboundEvent."""
        data = {
            "type": "inbound",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "telegram:user1",
            "content": "hello",
            "timestamp": 123.0,
            "retry_count": 1,
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)
        assert event.session_id == "s1"
        assert event.retry_count == 1

    def test_deserialize_outbound_event(self):
        """deserialize_event should create correct OutboundEvent."""
        data = {
            "type": "outbound",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:pickle",
            "content": "response",
            "timestamp": 123.0,
            "error": "test error",
        }
        event = deserialize_event(data)
        assert isinstance(event, OutboundEvent)
        assert event.error == "test error"

    def test_deserialize_dispatch_event(self):
        """deserialize_event should create correct DispatchEvent."""
        data = {
            "type": "dispatch",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:cookie",
            "content": "task",
            "timestamp": 123.0,
            "parent_session_id": "parent1",
            "retry_count": 0,
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchEvent)
        assert event.parent_session_id == "parent1"

    def test_deserialize_dispatch_result_event(self):
        """deserialize_event should create correct DispatchResultEvent."""
        data = {
            "type": "dispatch_result",
            "session_id": "s1",
            "agent_id": "a1",
            "source": "agent:sub",
            "content": "result",
            "timestamp": 123.0,
            "error": None,
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchResultEvent)

    def test_deserialize_unknown_type_raises(self):
        """deserialize_event should raise for unknown type."""
        data = {"type": "unknown", "session_id": "s1"}
        try:
            deserialize_event(data)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown event type" in str(e)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_events.py -v`
Expected: FAIL - tests don't exist yet or existing tests fail

**Step 3: Refactor Event base class**

Replace the old `Event` class and the four typed event classes with:

```python
"""Event types and data classes for the event bus."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, ClassVar

from picklebot.messagebus.base import MessageContext


class EventType(str, Enum):
    """Types of events in the system."""

    INBOUND = "inbound"  # External work entering the system (platforms, cron, retry)
    OUTBOUND = "outbound"  # Agent responses to deliver to platforms
    STATUS = "status"  # Status updates
    DISPATCH = "dispatch"  # Internal agent-to-agent delegation
    DISPATCH_RESULT = "dispatch_result"  # Result of a dispatched job


class Source:
    """Factory for creating typed event sources.

    Source format: "<type>:<identifier>" or just "<type>" for system sources.

    Examples:
        Source.agent("pickle")       -> "agent:pickle"
        Source.platform("telegram", "user_123") -> "telegram:user_123"
    """

    @staticmethod
    def agent(agent_id: str) -> str:
        """Create source for agent-generated events."""
        return f"agent:{agent_id}"

    @staticmethod
    def platform(platform: str, user_id: str) -> str:
        """Create source for platform-originated events."""
        return f"{platform}:{user_id}"

    @staticmethod
    def cron(cron_id: str) -> str:
        """Create source for cron-triggered events."""
        return f"cron:{cron_id}"

    @staticmethod
    def retry() -> str:
        """Create source for retry events."""
        return "retry"


def _serialize_context(context: MessageContext | None) -> dict[str, Any] | None:
    """Serialize a MessageContext to a dictionary."""
    if context is None:
        return None

    # Get the class name to identify the context type
    context_type = type(context).__name__

    # Extract dataclass fields if it's a dataclass
    if hasattr(context, "__dataclass_fields__"):
        data = {}
        for field_name in context.__dataclass_fields__:
            data[field_name] = getattr(context, field_name)
        return {"type": context_type, "data": data}

    return {"type": context_type, "data": {}}


def _deserialize_context(data: dict[str, Any] | None) -> MessageContext | None:
    """Deserialize a dictionary back to a MessageContext."""
    if data is None:
        return None

    context_type = data.get("type")
    context_data = data.get("data", {})

    # Import here to avoid circular imports
    if context_type == "TelegramContext":
        from picklebot.messagebus.telegram_bus import TelegramContext

        return TelegramContext(**context_data)
    elif context_type == "DiscordContext":
        from picklebot.messagebus.discord_bus import DiscordContext

        return DiscordContext(**context_data)
    elif context_type == "CliContext":
        from picklebot.messagebus.cli_bus import CliContext

        return CliContext(**context_data)

    return None


@dataclass
class Event:
    """Base class for all events with common fields and serialization."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float = field(default_factory=time.time)

    @property
    def type(self) -> EventType:
        """Return the event type. Subclasses must override."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize event from dictionary."""
        data = data.copy()
        data.pop("type", None)
        return cls(**data)


@dataclass
class InboundEvent(Event):
    """Event for external work entering the system (platforms, cron, retry)."""

    context: MessageContext | None = None
    retry_count: int = 0

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.INBOUND

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary with context handling."""
        data = super().to_dict()
        data["context"] = _serialize_context(self.context)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboundEvent":
        """Deserialize event from dictionary with context handling."""
        data = data.copy()
        data.pop("type", None)
        data["context"] = _deserialize_context(data.get("context"))
        return cls(**data)


@dataclass
class OutboundEvent(Event):
    """Event for agent responses to deliver to platforms."""

    error: str | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.OUTBOUND


@dataclass
class DispatchEvent(Event):
    """Event for internal agent-to-agent delegation."""

    parent_session_id: str = ""
    retry_count: int = 0

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.DISPATCH


@dataclass
class DispatchResultEvent(Event):
    """Event for result of a dispatched job."""

    error: str | None = None

    @property
    def type(self) -> EventType:
        """Return the event type."""
        return EventType.DISPATCH_RESULT


# Registry for deserialization
_EVENT_CLASSES: dict[EventType, type[Event]] = {
    EventType.INBOUND: InboundEvent,
    EventType.OUTBOUND: OutboundEvent,
    EventType.DISPATCH: DispatchEvent,
    EventType.DISPATCH_RESULT: DispatchResultEvent,
}


def serialize_event(event: Event) -> dict[str, Any]:
    """Serialize any event type to dict."""
    return event.to_dict()


def deserialize_event(data: dict[str, Any]) -> Event:
    """Deserialize dict to appropriate event type."""
    event_type_str = data.get("type")

    try:
        event_type = EventType(event_type_str)
    except ValueError:
        raise ValueError(f"Unknown event type: {event_type_str}")

    cls = _EVENT_CLASSES.get(event_type)
    if cls is None:
        raise ValueError(f"Unknown event type: {event_type_str}")

    return cls.from_dict(data)
```

Add the missing import at the top:

```python
import time
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_events.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/events.py tests/core/test_events.py
git commit -m "refactor: use inheritance for event classes

- Add Event base class with auto-timestamp and serialization
- Simplify typed event classes to only define specific fields
- Replace if-elif chain with registry for deserialization
- Remove TypedEvent alias (use Event directly)"
```

---

### Task 2: Update EventBus Imports

**Files:**
- Modify: `src/picklebot/core/eventbus.py`
- Test: existing tests

**Step 1: Update imports and type annotations**

In `src/picklebot/core/eventbus.py`, update the imports (lines 12-20):

```python
from .events import (
    Event,
    EventType,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    deserialize_event,
)
```

Remove the `AnyEvent` type alias (line 28) and replace all usages of `AnyEvent` with `Event`:

```python
# Remove this line:
# AnyEvent = Union[Event, InboundEvent, OutboundEvent, DispatchEvent, DispatchResultEvent]

# Change Handler type to:
Handler = Callable[[Event], Awaitable[None]]
```

Update the queue type annotation (line 43):
```python
self._queue: asyncio.Queue[Event] = asyncio.Queue()
```

**Step 2: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/core/eventbus.py
git commit -m "refactor(eventbus): simplify type annotations to use Event base class"
```

---

### Task 3: Update Worker Imports

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Modify: `src/picklebot/server/messagebus_worker.py`
- Modify: `src/picklebot/server/cron_worker.py`
- Modify: `src/picklebot/server/delivery_worker.py`
- Test: existing tests

**Step 1: Update agent_worker.py imports**

Change lines 11-19 in `src/picklebot/server/agent_worker.py`:

```python
from picklebot.core.events import (
    Event,
    EventType,
    Source,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
)
```

Remove `ProcessableEvent` type alias (line 33) - replace usages with `InboundEvent | DispatchEvent` inline or keep as is (it still works since it's just a union of the typed classes).

**Step 2: Update messagebus_worker.py imports**

Change line 9 in `src/picklebot/server/messagebus_worker.py`:
```python
from picklebot.core.events import Event, InboundEvent, Source
```

**Step 3: Update cron_worker.py imports**

Change line 14 in `src/picklebot/server/cron_worker.py`:
```python
from picklebot.core.events import Event, InboundEvent, Source
```

**Step 4: Update delivery_worker.py imports**

Check and update imports similarly.

**Step 5: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/server/agent_worker.py \
        src/picklebot/server/messagebus_worker.py \
        src/picklebot/server/cron_worker.py \
        src/picklebot/server/delivery_worker.py
git commit -m "refactor(workers): update event imports after refactor"
```

---

### Task 4: Update Tool Imports

**Files:**
- Modify: `src/picklebot/tools/subagent_tool.py`
- Modify: `src/picklebot/tools/post_message_tool.py`
- Test: existing tests

**Step 1: Update subagent_tool.py imports**

Change line 8 in `src/picklebot/tools/subagent_tool.py`:
```python
from picklebot.core.events import DispatchEvent, DispatchResultEvent, Event, Source
```

Update the type hint on line 104:
```python
async def handle_result(event: Event) -> None:
```

**Step 2: Update post_message_tool.py imports**

Change line 6 in `src/picklebot/tools/post_message_tool.py`:
```python
from picklebot.core.events import Event, OutboundEvent, Source
```

**Step 3: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/picklebot/tools/subagent_tool.py \
        src/picklebot/tools/post_message_tool.py
git commit -m "refactor(tools): update event imports after refactor"
```

---

### Task 5: Final Verification

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

**Step 2: Run linting**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Manual smoke test**

Run: `uv run picklebot chat -a pickle`
Send a message and verify it works.

**Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address any remaining issues from event refactor"
```
