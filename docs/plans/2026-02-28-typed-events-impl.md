# Typed Events Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace loose metadata dict with specialized typed event classes for better type safety and clearer contracts.

**Architecture:** Four event types (InboundEvent, OutboundEvent, DispatchEvent, DispatchResultEvent) with explicit fields. Event flow: INBOUND→OUTBOUND, DISPATCH→DISPATCH_RESULT. Retries requeue same event type with incremented retry_count and content=".".

**Tech Stack:** Python dataclasses, typing unions, existing MessageContext types

---

## Task 1: Create Typed Event Classes

**Files:**
- Modify: `src/picklebot/core/events.py`
- Test: `tests/events/test_types.py`

### Step 1: Write the failing tests

Update `tests/events/test_types.py`:

```python
# tests/events/test_types.py
import time
import dataclasses

import pytest

from picklebot.core.events import (
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    EventType,
    Source,
)
from picklebot.messagebus.telegram_bus import TelegramContext
from picklebot.messagebus.discord_bus import DiscordContext


class TestInboundEvent:
    """Tests for InboundEvent."""

    def test_inbound_event_creation(self):
        ctx = TelegramContext(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="telegram:123",
            content="Hello",
            timestamp=12345.0,
            retry_count=0,
            context=ctx,
        )
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert event.source == "telegram:123"
        assert event.content == "Hello"
        assert event.timestamp == 12345.0
        assert event.retry_count == 0
        assert event.context == ctx

    def test_inbound_event_defaults(self):
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="cli:cli-user",
            content="Hi",
            timestamp=12345.0,
        )
        assert event.retry_count == 0
        assert event.context is None

    def test_inbound_event_to_dict(self):
        ctx = TelegramContext(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="telegram:123",
            content="Hello",
            timestamp=12345.0,
            context=ctx,
        )
        result = event.to_dict()
        assert result["type"] == "inbound"
        assert result["session_id"] == "sess-1"
        assert result["agent_id"] == "pickle"
        assert result["context"]["type"] == "TelegramContext"

    def test_inbound_event_from_dict(self):
        data = {
            "type": "inbound",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "telegram:123",
            "content": "Hello",
            "timestamp": 12345.0,
            "retry_count": 1,
            "context": {
                "type": "TelegramContext",
                "data": {"user_id": "123", "chat_id": "456"},
            },
        }
        event = InboundEvent.from_dict(data)
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert isinstance(event.context, TelegramContext)
        assert event.context.chat_id == "456"


class TestOutboundEvent:
    """Tests for OutboundEvent."""

    def test_outbound_event_creation(self):
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="agent:pickle",
            content="Response",
            timestamp=12345.0,
        )
        assert event.session_id == "sess-1"
        assert event.agent_id == "pickle"
        assert event.error is None

    def test_outbound_event_with_error(self):
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="agent:pickle",
            content="",
            timestamp=12345.0,
            error="Something failed",
        )
        assert event.error == "Something failed"

    def test_outbound_event_serialization(self):
        event = OutboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="agent:pickle",
            content="Response",
            timestamp=12345.0,
            error="test error",
        )
        data = event.to_dict()
        assert data["type"] == "outbound"
        assert data["error"] == "test error"

        restored = OutboundEvent.from_dict(data)
        assert restored.error == "test error"


class TestDispatchEvent:
    """Tests for DispatchEvent."""

    def test_dispatch_event_creation(self):
        event = DispatchEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:pickle",
            content="Remember this",
            timestamp=12345.0,
            retry_count=0,
            parent_session_id="parent-sess-1",
        )
        assert event.session_id == "job-1"
        assert event.agent_id == "cookie"
        assert event.parent_session_id == "parent-sess-1"

    def test_dispatch_event_serialization(self):
        event = DispatchEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:pickle",
            content="Task",
            timestamp=12345.0,
            parent_session_id="parent-1",
        )
        data = event.to_dict()
        assert data["type"] == "dispatch"
        assert data["parent_session_id"] == "parent-1"

        restored = DispatchEvent.from_dict(data)
        assert restored.parent_session_id == "parent-1"


class TestDispatchResultEvent:
    """Tests for DispatchResultEvent."""

    def test_dispatch_result_event_creation(self):
        event = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:cookie",
            content="Done",
            timestamp=12345.0,
        )
        assert event.session_id == "job-1"
        assert event.error is None

    def test_dispatch_result_event_with_error(self):
        event = DispatchResultEvent(
            session_id="job-1",
            agent_id="cookie",
            source="agent:cookie",
            content="",
            timestamp=12345.0,
            error="Failed",
        )
        assert event.error == "Failed"


class TestEventTypeEnum:
    """Tests for EventType enum (still needed for serialization)."""

    def test_event_type_values(self):
        assert EventType.INBOUND.value == "inbound"
        assert EventType.OUTBOUND.value == "outbound"
        assert EventType.DISPATCH.value == "dispatch"
        assert EventType.DISPATCH_RESULT.value == "dispatch_result"


class TestSource:
    """Tests for Source factory methods."""

    def test_source_agent(self):
        assert Source.agent("pickle") == "agent:pickle"

    def test_source_platform(self):
        assert Source.platform("telegram", "user_123") == "telegram:user_123"

    def test_source_cron(self):
        assert Source.cron("daily") == "cron:daily"
```

### Step 2: Run tests to verify they fail

Run: `uv run pytest tests/events/test_types.py -v`
Expected: FAIL with import errors and missing classes

### Step 3: Write the typed event classes

Replace `src/picklebot/core/events.py`:

```python
"""Typed event classes for the event bus."""

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

from picklebot.messagebus.base import MessageContext


class EventType(str, Enum):
    """Types of events in the system (for serialization)."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    STATUS = "status"
    DISPATCH = "dispatch"
    DISPATCH_RESULT = "dispatch_result"


class Source:
    """Factory for creating typed event sources."""

    @staticmethod
    def agent(agent_id: str) -> str:
        return f"agent:{agent_id}"

    @staticmethod
    def platform(platform: str, user_id: str) -> str:
        return f"{platform}:{user_id}"

    @staticmethod
    def cron(cron_id: str) -> str:
        return f"cron:{cron_id}"

    @staticmethod
    def retry() -> str:
        return "retry"


def _serialize_context(context: MessageContext | None) -> dict[str, Any] | None:
    """Serialize MessageContext to dict for storage."""
    if context is None:
        return None
    return {
        "type": type(context).__name__,
        "data": dataclasses.asdict(context),
    }


def _deserialize_context(data: dict[str, Any] | None) -> MessageContext | None:
    """Deserialize MessageContext from dict."""
    if data is None:
        return None

    context_type = data.get("type")
    context_data = data.get("data", {})

    # Lazy import to avoid circular dependency
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
class InboundEvent:
    """External work entering the system (platforms, cron, retry)."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    retry_count: int = 0
    context: MessageContext | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": EventType.INBOUND.value,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "context": _serialize_context(self.context),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboundEvent":
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            retry_count=data.get("retry_count", 0),
            context=_deserialize_context(data.get("context")),
        )


@dataclass
class OutboundEvent:
    """Agent response to deliver to platforms."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "type": EventType.OUTBOUND.value,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.error is not None:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutboundEvent":
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            error=data.get("error"),
        )


@dataclass
class DispatchEvent:
    """Internal agent-to-agent delegation."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    parent_session_id: str
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": EventType.DISPATCH.value,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
            "parent_session_id": self.parent_session_id,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispatchEvent":
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            parent_session_id=data["parent_session_id"],
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class DispatchResultEvent:
    """Result of a dispatched job."""

    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "type": EventType.DISPATCH_RESULT.value,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.error is not None:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispatchResultEvent":
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            source=data["source"],
            content=data["content"],
            timestamp=data["timestamp"],
            error=data.get("error"),
        )


# Type alias for all events
Event = Union[InboundEvent, OutboundEvent, DispatchEvent, DispatchResultEvent]
```

### Step 4: Run tests to verify they pass

Run: `uv run pytest tests/events/test_types.py -v`
Expected: PASS

### Step 5: Commit

```bash
git add src/picklebot/core/events.py tests/events/test_types.py
git commit -m "feat(events): add typed event classes (InboundEvent, OutboundEvent, DispatchEvent, DispatchResultEvent)"
```

---

## Task 2: Add Event Serialization Helper

**Files:**
- Modify: `src/picklebot/core/events.py`
- Test: `tests/events/test_types.py`

### Step 1: Add serialization helper tests

Add to `tests/events/test_types.py`:

```python
class TestEventSerialization:
    """Tests for serialize/deserialize_event helpers."""

    def test_serialize_inbound_event(self):
        ctx = TelegramContext(user_id="123", chat_id="456")
        event = InboundEvent(
            session_id="sess-1",
            agent_id="pickle",
            source="telegram:123",
            content="Hello",
            timestamp=12345.0,
            context=ctx,
        )
        data = serialize_event(event)
        assert data["type"] == "inbound"

    def test_deserialize_inbound_event(self):
        data = {
            "type": "inbound",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "telegram:123",
            "content": "Hello",
            "timestamp": 12345.0,
            "context": {
                "type": "TelegramContext",
                "data": {"user_id": "123", "chat_id": "456"},
            },
        }
        event = deserialize_event(data)
        assert isinstance(event, InboundEvent)
        assert event.agent_id == "pickle"

    def test_deserialize_outbound_event(self):
        data = {
            "type": "outbound",
            "session_id": "sess-1",
            "agent_id": "pickle",
            "source": "agent:pickle",
            "content": "Response",
            "timestamp": 12345.0,
            "error": "test",
        }
        event = deserialize_event(data)
        assert isinstance(event, OutboundEvent)
        assert event.error == "test"

    def test_deserialize_dispatch_event(self):
        data = {
            "type": "dispatch",
            "session_id": "job-1",
            "agent_id": "cookie",
            "source": "agent:pickle",
            "content": "Task",
            "timestamp": 12345.0,
            "parent_session_id": "parent-1",
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchEvent)
        assert event.parent_session_id == "parent-1"

    def test_deserialize_dispatch_result_event(self):
        data = {
            "type": "dispatch_result",
            "session_id": "job-1",
            "agent_id": "cookie",
            "source": "agent:cookie",
            "content": "Done",
            "timestamp": 12345.0,
        }
        event = deserialize_event(data)
        assert isinstance(event, DispatchResultEvent)
```

### Step 2: Run tests to verify they fail

Run: `uv run pytest tests/events/test_types.py::TestEventSerialization -v`
Expected: FAIL with import errors

### Step 3: Add serialization helpers

Add to `src/picklebot/core/events.py` (after the event classes):

```python
def serialize_event(event: Event) -> dict[str, Any]:
    """Serialize any event type to dict."""
    return event.to_dict()


def deserialize_event(data: dict[str, Any]) -> Event:
    """Deserialize dict to appropriate event type."""
    event_type = data.get("type")

    if event_type == EventType.INBOUND.value:
        return InboundEvent.from_dict(data)
    elif event_type == EventType.OUTBOUND.value:
        return OutboundEvent.from_dict(data)
    elif event_type == EventType.DISPATCH.value:
        return DispatchEvent.from_dict(data)
    elif event_type == EventType.DISPATCH_RESULT.value:
        return DispatchResultEvent.from_dict(data)
    else:
        raise ValueError(f"Unknown event type: {event_type}")
```

### Step 4: Run tests to verify they pass

Run: `uv run pytest tests/events/test_types.py::TestEventSerialization -v`
Expected: PASS

### Step 5: Commit

```bash
git add src/picklebot/core/events.py tests/events/test_types.py
git commit -m "feat(events): add serialize_event and deserialize_event helpers"
```

---

## Task 3: Update AgentWorker to Use Typed Events

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Test: `tests/server/test_agent_worker.py`

### Step 1: Update test helper to use typed events

Update `make_event` helper in `tests/server/test_agent_worker.py`:

```python
from picklebot.core.events import (
    EventType,
    InboundEvent,
    DispatchEvent,
    Event,
)


def make_inbound_event(
    content: str = "Test",
    session_id: str = "",
    agent_id: str = "test-agent",
    retry_count: int = 0,
) -> InboundEvent:
    """Helper to create an InboundEvent for testing."""
    return InboundEvent(
        session_id=session_id,
        agent_id=agent_id,
        source="test:platform",
        content=content,
        timestamp=time.time(),
        retry_count=retry_count,
    )


def make_dispatch_event(
    content: str = "Test",
    session_id: str = "",
    agent_id: str = "test-agent",
    retry_count: int = 0,
    parent_session_id: str = "parent-1",
) -> DispatchEvent:
    """Helper to create a DispatchEvent for testing."""
    return DispatchEvent(
        session_id=session_id,
        agent_id=agent_id,
        source="agent:caller",
        content=content,
        timestamp=time.time(),
        retry_count=retry_count,
        parent_session_id=parent_session_id,
    )
```

### Step 2: Update AgentWorker imports and SessionExecutor

Replace `src/picklebot/server/agent_worker.py`:

```python
"""Agent worker for executing agent jobs."""

import asyncio
import dataclasses
import logging
import time
from typing import TYPE_CHECKING

from .worker import SubscriberWorker
from picklebot.core.agent import Agent, SessionMode
from picklebot.core.events import (
    Event,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    Source,
    serialize_event,
    deserialize_event,
)
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef


MAX_RETRIES = 3

logger = logging.getLogger(__name__)


class SessionExecutor:
    """Executes a single agent session from an event."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        event: InboundEvent | DispatchEvent,
        semaphore: asyncio.Semaphore,
    ):
        self.context = context
        self.agent_def = agent_def
        self.event = event
        self.semaphore = semaphore

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
                    session = agent.new_session(SessionMode.CHAT, session_id=session_id)
            else:
                session = agent.new_session(SessionMode.CHAT)
                session_id = session.session_id

            response = await session.chat(self.event.content)
            logger.info(f"Session completed: {session_id}")

            # Publish appropriate result event
            result_event = self._create_result_event(
                session_id=session_id,
                content=response,
            )
            await self.context.eventbus.publish(result_event)

        except Exception as e:
            logger.error(f"Session failed: {e}")

            if self.event.retry_count < MAX_RETRIES:
                # Requeue with incremented retry count
                retry_event = dataclasses.replace(
                    self.event,
                    retry_count=self.event.retry_count + 1,
                    content=".",
                )
                await self.context.eventbus.publish(retry_event)
            else:
                # Publish result with error
                result_event = self._create_result_event(
                    session_id=session_id or "",
                    content="",
                    error=str(e),
                )
                await self.context.eventbus.publish(result_event)

    def _create_result_event(
        self,
        session_id: str,
        content: str,
        error: str | None = None,
    ) -> OutboundEvent | DispatchResultEvent:
        """Create the appropriate result event based on input type."""
        if isinstance(self.event, DispatchEvent):
            return DispatchResultEvent(
                session_id=session_id,
                agent_id=self.agent_def.id,
                source=Source.agent(self.agent_def.id),
                content=content,
                timestamp=time.time(),
                error=error,
            )
        else:
            return OutboundEvent(
                session_id=session_id,
                agent_id=self.agent_def.id,
                source=Source.agent(self.agent_def.id),
                content=content,
                timestamp=time.time(),
                error=error,
            )


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

        # Subscribe to typed events via EventBus
        # Note: EventBus still uses EventType enum for subscription routing
        from picklebot.core.events import EventType
        self.context.eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
        self.context.eventbus.subscribe(EventType.DISPATCH, self.handle_dispatch)
        self.logger.info("AgentWorker subscribed to INBOUND and DISPATCH events")

    async def handle_inbound(self, event: Event) -> None:
        """Handle InboundEvent (from platforms, cron, retries)."""
        if not isinstance(event, InboundEvent):
            return
        await self._dispatch_event(event)

    async def handle_dispatch(self, event: Event) -> None:
        """Handle DispatchEvent (from subagent calls)."""
        if not isinstance(event, DispatchEvent):
            return
        await self._dispatch_event(event)

    async def _dispatch_event(self, event: InboundEvent | DispatchEvent) -> None:
        """Create executor task for event."""
        agent_id = event.agent_id

        try:
            agent_def = self.context.agent_loader.load(agent_id)
        except DefNotFoundError as e:
            logger.error(f"Agent not found: {agent_id}: {e}")
            # Publish error result
            result_event = self._create_error_result(event, str(e))
            await self.context.eventbus.publish(result_event)
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(SessionExecutor(self.context, agent_def, event, sem).run())
        self._maybe_cleanup_semaphores()

    def _create_error_result(
        self, event: InboundEvent | DispatchEvent, error: str
    ) -> OutboundEvent | DispatchResultEvent:
        """Create error result event."""
        if isinstance(event, DispatchEvent):
            return DispatchResultEvent(
                session_id=event.session_id,
                agent_id="dispatcher",
                source=Source.agent("dispatcher"),
                content="",
                timestamp=time.time(),
                error=error,
            )
        else:
            return OutboundEvent(
                session_id=event.session_id,
                agent_id="dispatcher",
                source=Source.agent("dispatcher"),
                content="",
                timestamp=time.time(),
                error=error,
            )

    def _get_or_create_semaphore(self, agent_def: "AgentDef") -> asyncio.Semaphore:
        if agent_def.id not in self._semaphores:
            self._semaphores[agent_def.id] = asyncio.Semaphore(
                agent_def.max_concurrency
            )
            logger.debug(
                f"Created semaphore for {agent_def.id} with value {agent_def.max_concurrency}"
            )
        return self._semaphores[agent_def.id]

    def _maybe_cleanup_semaphores(self) -> None:
        if len(self._semaphores) <= self.CLEANUP_THRESHOLD:
            return

        existing = {a.id for a in self.context.agent_loader.discover_agents()}
        stale = set(self._semaphores.keys()) - existing
        for agent_id in stale:
            del self._semaphores[agent_id]
            logger.debug(f"Cleaned up semaphore for deleted agent: {agent_id}")


# Backward compatibility alias
AgentDispatcher = AgentWorker
```

### Step 3: Update tests to use typed events

Update test assertions in `tests/server/test_agent_worker.py` to use typed event fields.

### Step 4: Run tests

Run: `uv run pytest tests/server/test_agent_worker.py -v`
Expected: Some failures due to test updates needed

### Step 5: Fix and commit

Fix any remaining test issues, then:

```bash
git add src/picklebot/server/agent_worker.py tests/server/test_agent_worker.py
git commit -m "refactor(agent_worker): use typed events with proper retry logic"
```

---

## Task 4: Update MessageBusWorker

**Files:**
- Modify: `src/picklebot/server/messagebus_worker.py`

### Step 1: Update MessageBusWorker to create InboundEvent

Update the event creation in `src/picklebot/server/messagebus_worker.py`:

```python
# Replace metadata dict with InboundEvent
from picklebot.core.events import InboundEvent, Source

# In the message handler:
event = InboundEvent(
    session_id=session_id,
    agent_id=self.context.config.default_agent,
    source=Source.platform(platform_name, context.user_id),
    content=message,
    timestamp=time.time(),
    context=context,  # Pass the MessageContext directly
)
await self.context.eventbus.publish(event)
```

### Step 2: Remove _extract_metadata method

The `context` field replaces the extracted metadata dict.

### Step 3: Commit

```bash
git add src/picklebot/server/messagebus_worker.py
git commit -m "refactor(messagebus_worker): create InboundEvent with typed context"
```

---

## Task 5: Update CronWorker

**Files:**
- Modify: `src/picklebot/server/cron_worker.py`

### Step 1: Update CronWorker to create InboundEvent

```python
from picklebot.core.events import InboundEvent, Source

# In cron job execution:
event = InboundEvent(
    session_id=session_id,
    agent_id=cron_def.agent,
    source=Source.cron(cron_def.id),
    content=prompt,
    timestamp=time.time(),
)
await self.context.eventbus.publish(event)
```

### Step 2: Commit

```bash
git add src/picklebot/server/cron_worker.py
git commit -m "refactor(cron_worker): create InboundEvent for cron jobs"
```

---

## Task 6: Update Subagent Tool

**Files:**
- Modify: `src/picklebot/tools/subagent_tool.py`

### Step 1: Update to create DispatchEvent and handle DispatchResultEvent

```python
from picklebot.core.events import DispatchEvent, DispatchResultEvent, Source, EventType

# In subagent_dispatch:
async def handle_result(event: Event) -> None:
    if isinstance(event, DispatchResultEvent) and event.session_id == job_id:
        if not result_future.done():
            if event.error:
                result_future.set_exception(Exception(event.error))
            else:
                result_future.set_result(event.content)

# Subscribe to DISPATCH_RESULT
shared_context.eventbus.subscribe(EventType.DISPATCH_RESULT, handle_result)

# Publish DispatchEvent
event = DispatchEvent(
    session_id=job_id,
    agent_id=agent_id,
    source=Source.agent(current_agent_id),
    content=user_message,
    timestamp=time.time(),
    parent_session_id=session.session_id,
)
await shared_context.eventbus.publish(event)
```

### Step 2: Commit

```bash
git add src/picklebot/tools/subagent_tool.py
git commit -m "refactor(subagent_tool): use DispatchEvent and DispatchResultEvent"
```

---

## Task 7: Update Post Message Tool

**Files:**
- Modify: `src/picklebot/tools/post_message_tool.py`

### Step 1: Update to create OutboundEvent

```python
from picklebot.core.events import OutboundEvent, Source

# In post_message tool:
event = OutboundEvent(
    session_id=session_id,
    agent_id=session.agent_id,
    source=Source.agent(session.agent_id),
    content=message,
    timestamp=time.time(),
)
await shared_context.eventbus.publish(event)
```

### Step 2: Commit

```bash
git add src/picklebot/tools/post_message_tool.py
git commit -m "refactor(post_message_tool): create OutboundEvent"
```

---

## Task 8: Update DeliveryWorker

**Files:**
- Modify: `src/picklebot/server/delivery_worker.py`

### Step 1: Update to handle OutboundEvent with context

```python
from picklebot.core.events import OutboundEvent, EventType

async def handle_event(self, event: Event) -> None:
    if not isinstance(event, OutboundEvent):
        return

    # Look up platform context from session store
    context = self._lookup_context(event.session_id)
    if context:
        await self._deliver(event.content, context)
```

### Step 2: Commit

```bash
git add src/picklebot/server/delivery_worker.py
git commit -m "refactor(delivery_worker): handle OutboundEvent"
```

---

## Task 9: Update EventBus Serialization

**Files:**
- Modify: `src/picklebot/core/eventbus.py`
- Test: `tests/events/test_bus.py`

### Step 1: Update EventBus to use serialize/deserialize_event

```python
from picklebot.core.events import (
    Event,
    EventType,
    serialize_event,
    deserialize_event,
)

# In persist_event:
def _persist_event(self, event: Event) -> None:
    if isinstance(event, OutboundEvent):
        data = serialize_event(event)
        # ... persist logic

# In load_events:
event = deserialize_event(data)
```

### Step 2: Commit

```bash
git add src/picklebot/core/eventbus.py tests/events/test_bus.py
git commit -m "refactor(eventbus): use serialize_event/deserialize_event"
```

---

## Task 10: Update Remaining Tests and Clean Up

**Files:**
- Multiple test files

### Step 1: Run all tests

Run: `uv run pytest -v`
Expected: Some failures due to event type changes

### Step 2: Fix remaining test failures

Update test files to use typed events:
- `tests/tools/test_subagent_tool.py`
- `tests/tools/test_post_message_tool.py`
- `tests/events/test_retry.py`
- `tests/events/test_bus_persistence.py`
- `tests/cli/test_chat_integration.py`

### Step 3: Remove old Event class

Once all tests pass, ensure the old `Event` class is fully replaced by the type alias.

### Step 4: Final test run

Run: `uv run pytest -v`
Expected: All tests PASS

### Step 5: Final commit

```bash
git add -A
git commit -m "refactor: complete typed event migration, update all tests"
```

---

## Summary

This plan migrates from a single `Event` class with loose `metadata: dict` to specialized typed event classes:

1. **InboundEvent** - External work with platform context
2. **OutboundEvent** - Agent responses with optional error
3. **DispatchEvent** - Agent-to-agent delegation with parent session
4. **DispatchResultEvent** - Dispatch results with optional error

Each task follows TDD: write test, run to fail, implement, run to pass, commit.
