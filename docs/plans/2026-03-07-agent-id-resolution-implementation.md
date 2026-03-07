# Agent-ID Resolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove agent_id from Event base class to ensure session affinity - agent bound to session, not routing.

**Architecture:** Events no longer carry agent_id. AgentWorker resolves agent from session metadata. RoutingTable only consulted for NEW sessions. Session becomes single source of truth.

**Tech Stack:** Python dataclasses, pytest, pickle-bot event system

---

## Overview

This refactoring removes the `agent_id` field from the `Event` base class across 7 source files and updates 20+ test files. The change ensures that when routing changes, existing sessions continue with their original agent (session affinity).

**Breaking Change:** Event serialization format changes (agent_id removed from events).

**Estimated Time:** 2-3 hours

---

## Task 1: Update Event Base Class

**Files:**
- Modify: `src/picklebot/core/events.py:149-160`
- Test: `tests/core/test_events.py` (create if needed)

**Step 1: Write failing test for Event without agent_id**

Create `tests/core/test_events.py`:

```python
"""Tests for Event classes after agent_id removal."""
import pytest
import time
from picklebot.core.events import (
    Event,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    AgentEventSource,
    CliEventSource,
)


def test_event_base_class_has_no_agent_id():
    """Event base class should not have agent_id field."""
    source = CliEventSource()
    event = Event(
        session_id="test-session",
        source=source,
        content="test content",
    )

    # Should not have agent_id attribute
    assert not hasattr(event, "agent_id")

    # Should have required fields
    assert event.session_id == "test-session"
    assert event.source == source
    assert event.content == "test content"
    assert isinstance(event.timestamp, float)


def test_inbound_event_creation():
    """InboundEvent should be creatable without agent_id."""
    source = CliEventSource()
    event = InboundEvent(
        session_id="test-session",
        source=source,
        content="user message",
        retry_count=0,
    )

    assert event.session_id == "test-session"
    assert event.source == source
    assert event.content == "user message"
    assert event.retry_count == 0
    assert not hasattr(event, "agent_id")


def test_dispatch_event_creation():
    """DispatchEvent should be creatable without agent_id."""
    source = AgentEventSource(agent_id="pickle")
    event = DispatchEvent(
        session_id="test-session",
        source=source,
        content="dispatch task",
        parent_session_id="parent-123",
    )

    assert event.session_id == "test-session"
    assert event.source == source
    assert event.content == "dispatch task"
    assert event.parent_session_id == "parent-123"
    assert not hasattr(event, "agent_id")


def test_outbound_event_creation():
    """OutboundEvent should be creatable without agent_id."""
    source = AgentEventSource(agent_id="pickle")
    event = OutboundEvent(
        session_id="test-session",
        source=source,
        content="response",
        error=None,
    )

    assert event.session_id == "test-session"
    assert event.source == source
    assert event.content == "response"
    assert event.error is None
    assert not hasattr(event, "agent_id")


def test_dispatch_result_event_creation():
    """DispatchResultEvent should be creatable without agent_id."""
    source = AgentEventSource(agent_id="pickle")
    event = DispatchResultEvent(
        session_id="test-session",
        source=source,
        content="result",
        error=None,
    )

    assert event.session_id == "test-session"
    assert event.source == source
    assert event.content == "result"
    assert event.error is None
    assert not hasattr(event, "agent_id")


def test_event_serialization_without_agent_id():
    """Event should serialize without agent_id field."""
    source = CliEventSource()
    event = InboundEvent(
        session_id="test-session",
        source=source,
        content="test",
    )

    data = event.to_dict()

    assert "agent_id" not in data
    assert data["session_id"] == "test-session"
    assert data["source"] == "platform-cli:cli-user"
    assert data["content"] == "test"
    assert data["type"] == "InboundEvent"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_events.py -v`

Expected: FAIL - Event class still has agent_id field

**Step 3: Remove agent_id from Event base class**

Modify `src/picklebot/core/events.py:149-160`:

```python
@dataclass
class Event:
    """Base class for all typed events.

    Subclasses define additional fields specific to that event type.
    Event type is determined by the class name for serialization.
    """

    session_id: str
    source: EventSource  # Changed from str to typed EventSource
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary, including type."""
        result: dict[str, Any] = {"type": self.__class__.__name__}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name == "source":
                result[field_name] = str(value)
            else:
                result[field_name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize event from dictionary."""
        kwargs = {}
        for k, v in data.items():
            if k == "type":
                continue
            if k == "source":
                kwargs[k] = EventSource.from_string(v)
            elif k in cls.__dataclass_fields__:
                kwargs[k] = v
        return cls(**kwargs)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_events.py -v`

Expected: PASS - All 6 tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/events.py tests/core/test_events.py
git commit -m "refactor: remove agent_id from Event base class

- Remove agent_id field from Event dataclass
- Session becomes single source of truth for agent identity
- Add comprehensive tests for all event types"
```

---

## Task 2: Update RoutingTable

**Files:**
- Modify: `src/picklebot/core/routing.py:79-106`
- Test: `tests/core/test_routing.py`

**Step 1: Write failing test for RoutingTable signature change**

Add to `tests/core/test_routing.py`:

```python
def test_get_or_create_session_id_no_agent_id_param(routing_table, mock_context):
    """get_or_create_session_id should not require agent_id parameter."""
    from picklebot.core.events import CliEventSource

    source = CliEventSource()

    # Should work without agent_id parameter
    session_id = routing_table.get_or_create_session_id(source)

    assert session_id is not None
    assert isinstance(session_id, str)


def test_get_or_create_session_id_resolves_agent_for_new_session(
    routing_table, mock_context
):
    """For new sessions, should resolve agent from routing table."""
    from picklebot.core.events import CliEventSource

    source = CliEventSource()
    source_str = str(source)

    # Mock routing to return 'cookie' agent
    mock_context.config.routing = {"bindings": []}
    mock_context.config.default_agent = "cookie"

    session_id = routing_table.get_or_create_session_id(source)

    # Verify session was created with 'cookie' agent
    session_info = mock_context.history_store.get_session_info(session_id)
    assert session_info.agent_id == "cookie"


def test_get_or_create_session_id_returns_cached_for_existing(
    routing_table, mock_context
):
    """For existing sessions, should return cached session_id."""
    from picklebot.core.events import CliEventSource

    source = CliEventSource()
    source_str = str(source)

    # Pre-create a session with 'pickle' agent
    from picklebot.core.agent import Agent
    agent_def = mock_context.agent_loader.load("pickle")
    agent = Agent(agent_def, mock_context)
    session = agent.new_session(source)

    # Cache it
    mock_context.config.set_runtime(
        f"sources.{source_str}", {"session_id": session.session_id}
    )

    # Now change routing to 'cookie'
    mock_context.config.default_agent = "cookie"

    # Should return existing 'pickle' session, not create new one
    returned_session_id = routing_table.get_or_create_session_id(source)

    assert returned_session_id == session.session_id

    # Verify it's still the 'pickle' session
    session_info = mock_context.history_store.get_session_info(returned_session_id)
    assert session_info.agent_id == "pickle"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_routing.py::test_get_or_create_session_id_no_agent_id_param -v`

Expected: FAIL - get_or_create_session_id still requires agent_id parameter

**Step 3: Update RoutingTable method signature**

Modify `src/picklebot/core/routing.py:79-106`:

```python
def get_or_create_session_id(self, source: EventSource) -> str:
    """Get existing or create new session_id for source.

    For existing sessions, returns cached session_id (session affinity).
    For new sessions, resolves agent from routing table.

    Args:
        source: Typed EventSource object

    Returns:
        session_id: Existing or newly created session identifier
    """
    source_str = str(source)

    # Check cache first (existing session)
    source_info = self._context.config.sources.get(source_str)
    if source_info:
        return source_info["session_id"]

    # New session: resolve agent from routing
    agent_id = self.resolve(source_str)

    # Create new session
    agent_def = self._context.agent_loader.load(agent_id)
    agent = Agent(agent_def, self._context)
    session = agent.new_session(source)

    # Cache the session
    self._context.config.set_runtime(
        f"sources.{source_str}", {"session_id": session.session_id}
    )

    return session.session_id
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_routing.py -v`

Expected: Some tests may fail due to signature change - that's expected

**Step 5: Update any failing tests in test_routing.py**

Find and fix any tests that call `get_or_create_session_id(source, agent_id)` - remove the agent_id parameter.

**Step 6: Commit**

```bash
git add src/picklebot/core/routing.py tests/core/test_routing.py
git commit -m "refactor: remove agent_id param from RoutingTable.get_or_create_session_id

- Method now resolves agent internally for new sessions
- Returns cached session_id for existing sessions (session affinity)
- Update tests to match new signature"
```

---

## Task 3: Update AgentWorker

**Files:**
- Modify: `src/picklebot/server/agent_worker.py:54-72, 136-158`
- Test: `tests/server/test_agent_worker.py`

**Step 1: Write failing test for agent resolution from session**

Add to `tests/server/test_agent_worker.py`:

```python
@pytest.mark.asyncio
async def test_dispatch_event_resolves_agent_from_session(context, mock_agent_loader):
    """AgentWorker should get agent_id from session, not event."""
    from picklebot.core.events import InboundEvent, CliEventSource
    from picklebot.core.agent import Agent
    from picklebot.server.agent_worker import AgentWorker

    # Create a session with 'pickle' agent
    source = CliEventSource()
    agent_def = mock_agent_loader.load("pickle")
    agent = Agent(agent_def, context)
    session = agent.new_session(source)

    # Create event WITHOUT agent_id field
    event = InboundEvent(
        session_id=session.session_id,
        source=source,
        content="test message",
    )

    worker = AgentWorker(context)

    # This should work - agent_id comes from session
    await worker.dispatch_event(event)

    # Verify 'pickle' agent was loaded (from session, not event)
    mock_agent_loader.load.assert_called_once_with("pickle")


@pytest.mark.asyncio
async def test_session_affinity_on_routing_change(context, mock_agent_loader):
    """When routing changes, existing session should keep original agent."""
    from picklebot.core.events import InboundEvent, CliEventSource
    from picklebot.core.agent import Agent
    from picklebot.server.agent_worker import AgentWorker

    # Create session with 'pickle' agent
    source = CliEventSource()
    agent_def = mock_agent_loader.load("pickle")
    agent = Agent(agent_def, context)
    session = agent.new_session(source)

    # Change default routing to 'cookie'
    context.config.default_agent = "cookie"

    # Send new message to existing session
    event = InboundEvent(
        session_id=session.session_id,
        source=source,
        content="new message",
    )

    worker = AgentWorker(context)
    await worker.dispatch_event(event)

    # Should still use 'pickle' (from session), not 'cookie' (from routing)
    mock_agent_loader.load.assert_called_once_with("pickle")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_agent_worker.py::test_dispatch_event_resolves_agent_from_session -v`

Expected: FAIL - dispatch_event still uses event.agent_id

**Step 3: Update AgentWorker to resolve agent from session**

Modify `src/picklebot/server/agent_worker.py:54-72`:

```python
async def dispatch_event(self, event: ProcessableEvent) -> None:
    """Create executor task for typed event."""
    # Get agent_id from session (single source of truth)
    session_info = self.context.history_store.get_session_info(event.session_id)
    if not session_info:
        logger.error(f"Session not found: {event.session_id}")
        return

    agent_id = session_info.agent_id

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
```

**Step 4: Update create_response_event to remove agent_id from events**

Modify `src/picklebot/server/agent_worker.py:136-158`:

```python
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
            source=AgentEventSource(agent_id),
            content=content,
            error=str(error) if error else None,
        )
    else:
        return OutboundEvent(
            session_id=event.session_id,
            source=AgentEventSource(agent_id),
            content=content,
            error=str(error) if error else None,
        )
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/server/test_agent_worker.py::test_dispatch_event_resolves_agent_from_session tests/server/test_agent_worker.py::test_session_affinity_on_routing_change -v`

Expected: PASS - Both tests pass

**Step 6: Commit**

```bash
git add src/picklebot/server/agent_worker.py tests/server/test_agent_worker.py
git commit -m "refactor: AgentWorker resolves agent from session

- Get agent_id from session_info instead of event
- Remove agent_id from OutboundEvent/DispatchResultEvent creation
- Add tests for session affinity"
```

---

## Task 4: Update ChannelWorker

**Files:**
- Modify: `src/picklebot/server/channel_worker.py:60-73`
- Test: `tests/server/test_channel_worker.py`

**Step 1: Write failing test for InboundEvent without agent_id**

Add to `tests/server/test_channel_worker.py`:

```python
@pytest.mark.asyncio
async def test_callback_creates_inbound_event_without_agent_id(context):
    """ChannelWorker callback should create InboundEvent without agent_id."""
    from picklebot.server.channel_worker import ChannelWorker
    from picklebot.core.events import InboundEvent, CliEventSource
    from unittest.mock import AsyncMock, patch

    worker = ChannelWorker(context)

    # Capture published events
    published_events = []
    async def capture_event(event):
        published_events.append(event)

    context.eventbus.subscribe(InboundEvent, capture_event)

    # Create callback
    callback = worker._create_callback("cli")

    # Send message
    source = CliEventSource()
    await callback("test message", source)

    # Verify event was published
    assert len(published_events) == 1
    event = published_events[0]

    # Should not have agent_id
    assert not hasattr(event, "agent_id")
    assert event.session_id is not None
    assert event.source == source
    assert event.content == "test message"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_channel_worker.py::test_callback_creates_inbound_event_without_agent_id -v`

Expected: FAIL - InboundEvent still being created with agent_id

**Step 3: Update ChannelWorker callback**

Modify `src/picklebot/server/channel_worker.py:60-73`:

```python
agent_id = self.context.routing_table.resolve(str(source))
session_id = self.context.routing_table.get_or_create_session_id(source)

# Publish INBOUND event with typed source
event = InboundEvent(
    session_id=session_id,
    source=source,
    content=message,
    timestamp=time.time(),
)
```

Wait - we need to remove the agent_id resolution line entirely. Let me correct:

```python
session_id = self.context.routing_table.get_or_create_session_id(source)

# Publish INBOUND event with typed source
event = InboundEvent(
    session_id=session_id,
    source=source,
    content=message,
    timestamp=time.time(),
)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_channel_worker.py::test_callback_creates_inbound_event_without_agent_id -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/channel_worker.py tests/server/test_channel_worker.py
git commit -m "refactor: remove agent_id from ChannelWorker InboundEvent creation

- Remove routing resolution (now inside get_or_create_session_id)
- Create InboundEvent without agent_id field"
```

---

## Task 5: Update CronWorker

**Files:**
- Modify: `src/picklebot/server/cron_worker.py:84-89`
- Test: `tests/server/test_cron_worker.py`

**Step 1: Write failing test for DispatchEvent without agent_id**

Add to `tests/server/test_cron_worker.py`:

```python
@pytest.mark.asyncio
async def test_cron_dispatch_creates_event_without_agent_id(context):
    """CronWorker should create DispatchEvent without agent_id."""
    from picklebot.server.cron_worker import CronWorker, find_due_jobs
    from picklebot.core.events import DispatchEvent
    from datetime import datetime

    worker = CronWorker(context)

    # Create a test cron
    from pathlib import Path
    cron_path = context.config.crons_path / "test-cron"
    cron_path.mkdir(parents=True, exist_ok=True)
    (cron_path / "CRON.md").write_text("""---
name: Test Cron
agent: pickle
schedule: "* * * * *"
---
Test task
""")

    # Capture dispatched events
    dispatched = []
    async def capture(event):
        dispatched.append(event)

    context.eventbus.subscribe(DispatchEvent, capture)

    # Run tick
    now = datetime.now().replace(second=0, microsecond=0)
    await worker._tick()

    # Find the event
    assert len(dispatched) == 1
    event = dispatched[0]

    # Should not have agent_id
    assert not hasattr(event, "agent_id")
    assert event.session_id is not None
    assert event.content == "Test task"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/server/test_cron_worker.py::test_cron_dispatch_creates_event_without_agent_id -v`

Expected: FAIL - DispatchEvent still being created with agent_id

**Step 3: Update CronWorker event creation**

Modify `src/picklebot/server/cron_worker.py:84-89`:

```python
event = DispatchEvent(
    session_id=session.session_id,
    source=CronEventSource(cron_id=cron_def.id),
    content=cron_def.prompt,
)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/server/test_cron_worker.py::test_cron_dispatch_creates_event_without_agent_id -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/server/cron_worker.py tests/server/test_cron_worker.py
git commit -m "refactor: remove agent_id from CronWorker DispatchEvent creation"
```

---

## Task 6: Update Subagent Tool

**Files:**
- Modify: `src/picklebot/tools/subagent_tool.py:122-129`
- Test: `tests/tools/test_subagent_tool.py`

**Step 1: Write failing test for DispatchEvent without agent_id**

Add to `tests/tools/test_subagent_tool.py`:

```python
@pytest.mark.asyncio
async def test_subagent_dispatch_creates_event_without_agent_id(context):
    """subagent_dispatch should create DispatchEvent without agent_id."""
    from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
    from picklebot.core.events import DispatchEvent
    from picklebot.core.agent import Agent, AgentSession
    from unittest.mock import AsyncMock

    # Create tool
    tool = create_subagent_dispatch_tool("pickle", context)
    assert tool is not None

    # Create mock session
    agent_def = context.agent_loader.load("pickle")
    agent = Agent(agent_def, context)
    from picklebot.core.events import CliEventSource
    source = CliEventSource()
    session = agent.new_session(source)

    # Capture dispatched events
    dispatched = []
    async def capture(event: DispatchEvent) -> None:
        dispatched.append(event)

    context.eventbus.subscribe(DispatchEvent, capture)

    # Start EventBus
    eventbus_task = asyncio.create_task(context.eventbus.run())

    try:
        # Execute tool
        result = await tool.func(
            agent_id="cookie",
            task="Test task",
            session=session,
        )

        # Wait for dispatch
        await asyncio.sleep(0.1)

        # Verify event
        assert len(dispatched) == 1
        event = dispatched[0]

        # Should not have agent_id
        assert not hasattr(event, "agent_id")
        assert event.content == "Test task"

    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_subagent_tool.py::test_subagent_dispatch_creates_event_without_agent_id -v`

Expected: FAIL - DispatchEvent still being created with agent_id

**Step 3: Update subagent_tool event creation**

Modify `src/picklebot/tools/subagent_tool.py:122-129`:

```python
event = DispatchEvent(
    session_id=session_id,
    source=AgentEventSource(agent_id=current_agent_id),
    content=user_message,
    timestamp=time.time(),
    parent_session_id=session.session_id,
)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_subagent_tool.py::test_subagent_dispatch_creates_event_without_agent_id -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/subagent_tool.py tests/tools/test_subagent_tool.py
git commit -m "refactor: remove agent_id from subagent_dispatch DispatchEvent creation"
```

---

## Task 7: Update Post Message Tool

**Files:**
- Modify: `src/picklebot/tools/post_message_tool.py:61-67`
- Test: `tests/tools/test_post_message_tool.py`

**Step 1: Write failing test for OutboundEvent without agent_id**

Add to `tests/tools/test_post_message_tool.py`:

```python
@pytest.mark.asyncio
async def test_post_message_creates_event_without_agent_id(context, mock_session):
    """post_message should create OutboundEvent without agent_id."""
    from picklebot.tools.post_message_tool import create_post_message_tool
    from picklebot.core.events import OutboundEvent

    tool = create_post_message_tool(context)
    assert tool is not None

    # Capture outbound events
    outbound = []
    async def capture(event: OutboundEvent) -> None:
        outbound.append(event)

    context.eventbus.subscribe(OutboundEvent, capture)

    # Start EventBus
    eventbus_task = asyncio.create_task(context.eventbus.run())

    try:
        # Execute tool
        result = await tool.func(
            content="Test message",
            session=mock_session,
        )

        # Wait for event
        await asyncio.sleep(0.1)

        # Verify event
        assert len(outbound) == 1
        event = outbound[0]

        # Should not have agent_id
        assert not hasattr(event, "agent_id")
        assert event.content == "Test message"

    finally:
        eventbus_task.cancel()
        try:
            await eventbus_task
        except asyncio.CancelledError:
            pass
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/tools/test_post_message_tool.py::test_post_message_creates_event_without_agent_id -v`

Expected: FAIL - OutboundEvent still being created with agent_id

**Step 3: Update post_message_tool event creation**

Modify `src/picklebot/tools/post_message_tool.py:61-67`:

```python
event = OutboundEvent(
    session_id=session.session_id,
    source=AgentEventSource(agent_id=session.agent.agent_def.id),
    content=content,
    timestamp=time.time(),
)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/tools/test_post_message_tool.py::test_post_message_creates_event_without_agent_id -v`

Expected: PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/post_message_tool.py tests/tools/test_post_message_tool.py
git commit -m "refactor: remove agent_id from post_message OutboundEvent creation"
```

---

## Task 8: Fix All Remaining Tests

**Files:**
- Multiple test files

**Step 1: Run all tests to find failures**

Run: `uv run pytest -x`

Expected: Multiple test failures due to agent_id removal

**Step 2: Fix each failing test**

For each failing test:
1. Find where event is created with agent_id
2. Remove agent_id parameter
3. If test expects agent_id in event, update assertions

Common patterns to fix:

```python
# OLD:
event = InboundEvent(
    session_id="test",
    agent_id="pickle",  # REMOVE
    source=source,
    content="test",
)

# NEW:
event = InboundEvent(
    session_id="test",
    source=source,
    content="test",
)
```

```python
# OLD:
assert event.agent_id == "pickle"  # REMOVE

# NEW:
# If you need agent_id, get it from session:
session_info = history_store.get_session_info(event.session_id)
assert session_info.agent_id == "pickle"
```

**Step 3: Run all tests again**

Run: `uv run pytest -v`

Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: update all tests for agent_id removal from events

- Remove agent_id from event creation across all test files
- Update assertions to get agent_id from session when needed
- All tests passing"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run complete test suite**

Run: `uv run pytest --tb=short`

Expected: All tests pass

**Step 2: Run with coverage (optional)**

Run: `uv run pytest --cov=src/picklebot --cov-report=term-missing`

Review coverage report for any missed changes.

**Step 3: Format and lint**

Run: `uv run black . && uv run ruff check .`

Fix any formatting or linting issues.

**Step 4: Final commit if needed**

```bash
git add .
git commit -m "chore: formatting and lint fixes"
```

---

## Task 10: Integration Testing

**Step 1: Manual test with routing change**

1. Start server: `uv run picklebot server`
2. Send message from CLI: `uv run picklebot chat`
3. Note the session_id and agent being used
4. Change routing in config to different agent
5. Send another message
6. Verify: Same agent continues (session affinity)
7. Use `/clear` command
8. Send another message
9. Verify: New agent from routing is used

**Step 2: Test with multiple platforms**

1. Start server with Telegram/Discord enabled
2. Start conversation on platform A
3. Change routing
4. Continue conversation on platform A - should keep original agent
5. Start new conversation on platform B - should use new routing

**Step 3: Document behavior**

Update `docs/features.md` routing section to document session affinity behavior.

---

## Success Criteria

After completing all tasks, verify:

- [ ] Event base class has no agent_id field
- [ ] All event subclasses work without agent_id
- [ ] AgentWorker resolves agent from session
- [ ] RoutingTable.get_or_create_session_id() has no agent_id parameter
- [ ] All event creators (5 locations) updated
- [ ] All tests pass (run `uv run pytest`)
- [ ] No formatting/linting errors
- [ ] Manual testing confirms session affinity
- [ ] Routing changes don't affect existing sessions
- [ ] `/clear` creates new session with current routing

---

## Rollback Plan

If issues arise in production:

1. Event queue may have old events with agent_id - clear before deployment
2. Sessions unaffected (already have agent_id in storage)
3. Can rollback code changes - no database migration to reverse

---

## Notes

- **Breaking change**: Event serialization format changes
- **No database migration**: Sessions already store agent_id
- **Session affinity**: Existing sessions keep original agent
- **User control**: `/clear` command to force new session with current routing
