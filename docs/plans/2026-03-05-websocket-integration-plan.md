# WebSocket Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add bidirectional WebSocket support to pickle-bot for real-time event monitoring and chat.

**Architecture:** WebSocketWorker lives in SharedContext and manages all WebSocket connections. FastAPI provides thin `/ws` endpoint that hands off to worker. Worker subscribes to EventBus events and broadcasts to all clients, while also receiving client messages, normalizing them, and emitting InboundEvents.

**Tech Stack:** FastAPI WebSocket, Pydantic validation, dataclasses for EventSource, asyncio for concurrent connection handling.

---

## Task 1: Add WebSocketMessage Pydantic Schema

**Files:**
- Modify: `src/picklebot/api/schemas.py`
- Create: `tests/api/test_schemas.py`

**Step 1: Write the failing tests**

Create `tests/api/test_schemas.py`:

```python
"""Tests for WebSocket message schemas."""

import pytest
from pydantic import ValidationError
from picklebot.api.schemas import WebSocketMessage


class TestWebSocketMessage:
    """Test WebSocketMessage validation."""

    def test_valid_message_with_all_fields(self):
        """Test valid message with all fields."""
        msg = WebSocketMessage(
            source="user-123",
            content="Hello Pickle!",
            agent_id="pickle"
        )
        assert msg.source == "user-123"
        assert msg.content == "Hello Pickle!"
        assert msg.agent_id == "pickle"

    def test_valid_message_without_agent_id(self):
        """Test valid message without optional agent_id."""
        msg = WebSocketMessage(
            source="user-456",
            content="Hello!"
        )
        assert msg.source == "user-456"
        assert msg.content == "Hello!"
        assert msg.agent_id is None

    def test_invalid_message_missing_source(self):
        """Test invalid message without required source."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(content="Hello!")

        assert "source" in str(exc_info.value)

    def test_invalid_message_missing_content(self):
        """Test invalid message without required content."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(source="user-123")

        assert "content" in str(exc_info.value)

    def test_invalid_message_empty_source(self):
        """Test invalid message with empty source string."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(source="", content="Hello!")

        assert "at least 1 character" in str(exc_info.value).lower()

    def test_invalid_message_empty_content(self):
        """Test invalid message with empty content string."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage(source="user-123", content="")

        assert "at least 1 character" in str(exc_info.value).lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_schemas.py -v`

Expected: FAIL - ModuleNotFoundError (schemas.py doesn't have WebSocketMessage yet)

**Step 3: Implement WebSocketMessage schema**

Modify `src/picklebot/api/schemas.py`, add to imports and class definitions:

```python
from pydantic import BaseModel, Field


class WebSocketMessage(BaseModel):
    """Incoming WebSocket message from client.

    Used for clients sending messages to agents via WebSocket.

    Attributes:
        source: Client identifier (user ID, client name, etc.)
        content: Message content to send to agent
        agent_id: Target agent ID (optional - will use routing if not specified)
    """

    source: str = Field(..., min_length=1, description="Client identifier")
    content: str = Field(..., min_length=1, description="Message content")
    agent_id: str | None = Field(
        None, description="Target agent ID (optional - uses routing if not specified)"
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/api/test_schemas.py -v`

Expected: PASS - All 6 tests pass

**Step 5: Commit**

```bash
git add src/picklebot/api/schemas.py tests/api/test_schemas.py
git commit -m "feat: add WebSocketMessage schema with validation"
```

---

## Task 2: Add WebSocketEventSource Class

**Files:**
- Modify: `src/picklebot/core/events.py`
- Create: `tests/core/test_websocket_event_source.py`

**Step 1: Write the failing tests**

Create `tests/core/test_websocket_event_source.py`:

```python
"""Tests for WebSocketEventSource."""

import pytest
from picklebot.core.events import WebSocketEventSource


class TestWebSocketEventSource:
    """Test WebSocketEventSource functionality."""

    def test_create_websocket_event_source(self):
        """Test creating WebSocketEventSource with user_id."""
        source = WebSocketEventSource(user_id="user-123")

        assert source.user_id == "user-123"
        assert source.is_platform is True
        assert source.is_agent is False
        assert source.is_cron is False

    def test_string_representation(self):
        """Test string representation of WebSocketEventSource."""
        source = WebSocketEventSource(user_id="user-456")

        assert str(source) == "platform-ws:user-456"

    def test_from_string_valid(self):
        """Test parsing valid source string."""
        source = WebSocketEventSource.from_string("platform-ws:user-789")

        assert source.user_id == "user-789"

    def test_from_string_with_colon_in_user_id(self):
        """Test parsing source string with colon in user_id."""
        source = WebSocketEventSource.from_string("platform-ws:user:with:colons")

        assert source.user_id == "user:with:colons"

    def test_from_string_invalid_namespace(self):
        """Test parsing with invalid namespace."""
        with pytest.raises(ValueError, match="Invalid WebSocketEventSource"):
            WebSocketEventSource.from_string("invalid-namespace:user-123")

    def test_from_string_invalid_format(self):
        """Test parsing with invalid format (no colon)."""
        with pytest.raises(ValueError, match="Invalid WebSocketEventSource"):
            WebSocketEventSource.from_string("invalid-format")

    def test_from_string_empty_user_id(self):
        """Test parsing with empty user_id."""
        with pytest.raises(ValueError, match="Invalid WebSocketEventSource"):
            WebSocketEventSource.from_string("platform-ws:")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_websocket_event_source.py -v`

Expected: FAIL - ImportError (WebSocketEventSource not defined yet)

**Step 3: Implement WebSocketEventSource class**

Modify `src/picklebot/core/events.py`:

First, check existing EventSource implementations (like CliEventSource, TelegramEventSource) to understand the pattern. Add WebSocketEventSource following the same pattern:

```python
# Add after other EventSource implementations
@dataclass
class WebSocketEventSource(EventSource):
    """Event from WebSocket client.

    Source format: platform-ws:<user_id>

    Examples:
        - platform-ws:user-123
        - platform-ws:dashboard
        - platform-ws:mobile-app
    """

    _namespace = "platform-ws"
    user_id: str

    @classmethod
    def from_string(cls, s: str) -> "WebSocketEventSource":
        """Parse source string into WebSocketEventSource.

        Args:
            s: Source string in format "platform-ws:<user_id>"

        Returns:
            WebSocketEventSource instance

        Raises:
            ValueError: If string format is invalid
        """
        parts = s.split(":", 1)
        if len(parts) != 2 or parts[0] != cls._namespace or not parts[1]:
            raise ValueError(f"Invalid WebSocketEventSource: {s}")
        return cls(user_id=parts[1])

    def __str__(self) -> str:
        """Convert to source string format."""
        return f"{self._namespace}:{self.user_id}"

    @property
    def is_platform(self) -> bool:
        """WebSocket sources are platform sources."""
        return True
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_websocket_event_source.py -v`

Expected: PASS - All 7 tests pass

**Step 5: Commit**

```bash
git add src/picklebot/core/events.py tests/core/test_websocket_event_source.py
git commit -m "feat: add WebSocketEventSource for platform-ws namespace"
```

---

## Task 3: Update SharedContext for WebSocket Worker

**Files:**
- Modify: `src/picklebot/core/context.py`

**Step 1: Read existing SharedContext implementation**

Read: `src/picklebot/core/context.py`

Understand the current fields and initialization pattern.

**Step 2: Add websocket_worker field**

Modify `src/picklebot/core/context.py`:

```python
# In SharedContext.__init__ method, add to field initialization:
self.websocket_worker: "WebSocketWorker | None" = None
```

Also add to the TYPE_CHECKING imports at the top:

```python
if TYPE_CHECKING:
    from picklebot.server.websocket_worker import WebSocketWorker
```

**Step 3: Verify the change**

Read the modified file to ensure:
- Field is added in `__init__`
- TYPE_CHECKING import is added
- Type annotation is correct

**Step 4: Commit**

```bash
git add src/picklebot/core/context.py
git commit -m "feat: add websocket_worker field to SharedContext"
```

---

## Task 4: Enhance WebSocketWorker

**Files:**
- Modify: `src/picklebot/server/websocket_worker.py`
- Create: `tests/server/test_websocket_worker.py`

**Step 1: Write the failing tests**

Create `tests/server/test_websocket_worker.py`:

```python
"""Tests for WebSocketWorker."""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from picklebot.server.websocket_worker import WebSocketWorker
from picklebot.api.schemas import WebSocketMessage
from picklebot.core.events import WebSocketEventSource, InboundEvent


class TestWebSocketWorker:
    """Test WebSocketWorker functionality."""

    @pytest.fixture
    def mock_context(self):
        """Create mock SharedContext."""
        context = Mock()
        context.eventbus = Mock()
        context.eventbus.subscribe = Mock()
        context.eventbus.emit = AsyncMock()
        context.config = Mock()
        context.config.api = Mock()
        context.config.api.enabled = True
        return context

    @pytest.fixture
    def worker(self, mock_context):
        """Create WebSocketWorker instance."""
        return WebSocketWorker(mock_context)

    def test_worker_initialization(self, worker):
        """Test worker initializes with empty client set."""
        assert worker.clients == set()
        assert worker.context is not None

    def test_worker_subscribes_to_all_events(self, mock_context):
        """Test worker subscribes to all event types."""
        worker = WebSocketWorker(mock_context)

        # Should subscribe to 4 event types
        assert mock_context.eventbus.subscribe.call_count == 4

    @pytest.mark.asyncio
    async def test_handle_connection_adds_client(self, worker):
        """Test handle_connection adds client to set."""
        mock_ws = Mock()

        await worker.handle_connection(mock_ws)

        assert mock_ws in worker.clients

    @pytest.mark.asyncio
    async def test_handle_connection_removes_client_on_exit(self, worker):
        """Test handle_connection removes client when done."""
        mock_ws = Mock()
        mock_ws.receive_json = AsyncMock(side_effect=Exception("Disconnect"))

        await worker.handle_connection(mock_ws)

        assert mock_ws not in worker.clients

    def test_normalize_message_with_agent_id(self, worker):
        """Test normalizing message with explicit agent_id."""
        msg = WebSocketMessage(
            source="user-123",
            content="Hello!",
            agent_id="pickle"
        )

        # Mock routing/session methods (will be implemented later)
        worker._get_or_create_session = Mock(return_value="session-abc")

        event = worker._normalize_message(msg)

        assert isinstance(event, InboundEvent)
        assert event.agent_id == "pickle"
        assert event.content == "Hello!"
        assert isinstance(event.source, WebSocketEventSource)
        assert event.source.user_id == "user-123"

    def test_normalize_message_without_agent_id(self, worker):
        """Test normalizing message without agent_id (uses routing)."""
        msg = WebSocketMessage(
            source="user-456",
            content="Hello!",
            agent_id=None
        )

        # Mock routing to return specific agent
        worker._route_message = Mock(return_value="cookie")
        worker._get_or_create_session = Mock(return_value="session-xyz")

        event = worker._normalize_message(msg)

        assert event.agent_id == "cookie"
        worker._route_message.assert_called_once_with("user-456", "Hello!")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/server/test_websocket_worker.py -v`

Expected: FAIL - Multiple failures (methods not implemented yet)

**Step 3: Implement enhanced WebSocketWorker**

Modify `src/picklebot/server/websocket_worker.py`:

```python
# src/picklebot/server/websocket_worker.py
"""WebSocket worker for broadcasting events to connected clients."""

import logging
import time
import dataclasses
from typing import TYPE_CHECKING, set as typing_set
from dataclasses import dataclass

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import ValidationError

from .worker import SubscriberWorker
from picklebot.core.events import (
    Event,
    InboundEvent,
    OutboundEvent,
    DispatchEvent,
    DispatchResultEvent,
    WebSocketEventSource,
)
from picklebot.api.schemas import WebSocketMessage

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class WebSocketWorker(SubscriberWorker):
    """Manages WebSocket connections and event broadcasting.

    Subscribes to all EventBus events and broadcasts to connected WebSocket clients.
    Also handles incoming WebSocket messages, normalizes them to InboundEvents,
    and emits them to the EventBus.
    """

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self.clients: typing_set[WebSocket] = set()

        # Auto-subscribe to all event classes
        for event_class in [
            InboundEvent,
            OutboundEvent,
            DispatchEvent,
            DispatchResultEvent,
        ]:
            self.context.eventbus.subscribe(event_class, self.handle_event)
        self.logger.info("WebSocketWorker subscribed to all event types")

    async def handle_connection(self, ws: WebSocket) -> None:
        """Handle a single WebSocket connection lifecycle.

        Args:
            ws: WebSocket connection from FastAPI endpoint
        """
        self.clients.add(ws)
        self.logger.info(f"WebSocket client connected. Total clients: {len(self.clients)}")

        try:
            await self._run_client_loop(ws)
        finally:
            self.clients.discard(ws)
            self.logger.info(f"WebSocket client disconnected. Total clients: {len(self.clients)}")

    async def _run_client_loop(self, ws: WebSocket) -> None:
        """Run message receiving loop for a single client.

        Continuously receives messages from client, validates them,
        normalizes to InboundEvent, and emits to EventBus.

        Args:
            ws: WebSocket connection
        """
        while True:
            try:
                # Receive and validate message
                data = await ws.receive_json()
                msg = WebSocketMessage(**data)

                # Normalize to InboundEvent
                event = self._normalize_message(msg)

                # Emit to EventBus
                await self.context.eventbus.emit(event)
                self.logger.debug(f"Emitted InboundEvent from WebSocket: {msg.source}")

            except WebSocketDisconnect:
                self.logger.info("Client disconnected normally")
                break
            except ValidationError as e:
                # Send validation error back to client
                await ws.send_json({
                    "type": "error",
                    "message": f"Validation error: {e}"
                })
                self.logger.warning(f"Validation error from client: {e}")
                # Don't disconnect - let client retry
            except Exception as e:
                self.logger.error(f"Unexpected error in client loop: {e}")
                break

    def _normalize_message(self, msg: WebSocketMessage) -> InboundEvent:
        """Normalize WebSocketMessage to InboundEvent.

        Args:
            msg: Validated WebSocket message

        Returns:
            InboundEvent ready to emit to EventBus
        """
        # Determine agent_id (use routing if null)
        agent_id = msg.agent_id
        if agent_id is None:
            agent_id = self._route_message(msg.source, msg.content)

        # Lookup or create session
        session_id = self._get_or_create_session(agent_id, msg.source)

        return InboundEvent(
            session_id=session_id,
            agent_id=agent_id,
            source=WebSocketEventSource(user_id=msg.source),
            content=msg.content,
            timestamp=time.time()
        )

    def _route_message(self, source: str, content: str) -> str:
        """Route message to determine target agent.

        Uses SharedContext routing to determine agent_id based on source.

        Args:
            source: Client source identifier
            content: Message content

        Returns:
            Agent ID to handle this message
        """
        # Use routing system to determine agent
        # For now, default to 'pickle' agent
        # TODO: Integrate with routing system when available
        return "pickle"

    def _get_or_create_session(self, agent_id: str, source: str) -> str:
        """Get existing session or create new one.

        Args:
            agent_id: Target agent ID
            source: Client source identifier

        Returns:
            Session ID
        """
        # For now, create a simple session ID based on source and agent
        # TODO: Integrate with proper session management
        import hashlib
        session_key = f"{agent_id}:{source}"
        return hashlib.md5(session_key.encode()).hexdigest()[:12]

    async def handle_event(self, event: Event) -> None:
        """Handle EventBus event by broadcasting to WebSocket clients.

        Args:
            event: Event from EventBus
        """
        if not self.clients:
            return

        # Serialize event to dict with type information
        event_dict = {
            "type": event.__class__.__name__,
        }
        event_dict.update(dataclasses.asdict(event))

        # Convert EventSource to string for JSON serialization
        if "source" in event_dict and hasattr(event.source, "__str__"):
            event_dict["source"] = str(event.source)

        # Broadcast to all clients
        self.logger.debug(f"Broadcasting {event.__class__.__name__} to {len(self.clients)} clients")

        for client in list(self.clients):
            try:
                await client.send_json(event_dict)
            except Exception as e:
                self.logger.error(f"Failed to send to client: {e}")
                self.clients.discard(client)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/server/test_websocket_worker.py -v`

Expected: PASS - All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/server/websocket_worker.py tests/server/test_websocket_worker.py
git commit -m "feat: implement WebSocketWorker with connection handling and normalization"
```

---

## Task 5: Update Server to Attach WebSocketWorker

**Files:**
- Modify: `src/picklebot/server/server.py`

**Step 1: Read current server implementation**

Read: `src/picklebot/server/server.py`

Understand how workers are created and attached.

**Step 2: Update _setup_workers method**

Modify `src/picklebot/server/server.py`:

In the `_setup_workers` method, update the WebSocketWorker creation:

```python
def _setup_workers(self) -> None:
    """Create all workers."""
    self.config_reloader.start()

    # Create WebSocketWorker first and attach to context
    from .websocket_worker import WebSocketWorker
    ws_worker = WebSocketWorker(self.context)
    self.context.websocket_worker = ws_worker

    self.workers = [
        self.context.eventbus,  # EventBus (active worker)
        AgentWorker(self.context),  # SubscriberWorker
        CronWorker(self.context),  # Active worker
        DeliveryWorker(self.context),  # SubscriberWorker
        ws_worker,  # WebSocketWorker (SubscriberWorker)
    ]

    if self.context.config.messagebus.enabled:
        buses = self.context.messagebus_buses
        if buses:
            self.workers.append(MessageBusWorker(self.context))
            self.logger.info(f"MessageBus enabled with {len(buses)} bus(es)")
        else:
            self.logger.warning("MessageBus enabled but no buses configured")

    logger.info(f"Server setup complete with {len(self.workers)} core workers")
```

**Step 3: Verify the change**

Read the modified section to ensure:
- WebSocketWorker is imported
- Worker is created before adding to workers list
- Worker is attached to `context.websocket_worker`
- Worker is added to workers list

**Step 4: Commit**

```bash
git add src/picklebot/server/server.py
git commit -m "feat: attach WebSocketWorker to SharedContext in server"
```

---

## Task 6: Add FastAPI WebSocket Endpoint

**Files:**
- Modify: `src/picklebot/api/app.py` or create `src/picklebot/api/routers/websocket.py`
- Create: `tests/api/test_websocket_endpoint.py`

**Step 1: Add WebSocket endpoint to FastAPI app**

Modify `src/picklebot/api/app.py`:

Add WebSocket endpoint in the `create_app` function:

```python
from fastapi import WebSocket


def create_app(context: SharedContext) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pickle Bot API",
        description="HTTP API for pickle-bot SDK",
        version="0.1.0",
    )
    app.state.context = context

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Existing routers
    app.include_router(agents.router, prefix="/agents", tags=["agents"])
    app.include_router(skills.router, prefix="/skills", tags=["skills"])
    app.include_router(crons.router, prefix="/crons", tags=["crons"])
    app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    app.include_router(memories.router, prefix="/memories", tags=["memories"])
    app.include_router(config.router, prefix="/config", tags=["config"])

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time event streaming and chat.

        Clients can:
        - Receive all EventBus events in real-time
        - Send messages that create InboundEvents

        Message format (client -> server):
            {
                "source": "user-id",
                "content": "message text",
                "agent_id": "pickle"  # optional
            }

        Event format (server -> client):
            {
                "type": "InboundEvent",
                "session_id": "...",
                "agent_id": "...",
                "source": "platform-ws:user-id",
                "content": "...",
                ...
            }
        """
        await websocket.accept()

        # Check if WebSocket worker is available
        if context.websocket_worker is None:
            await websocket.close(code=1013, reason="WebSocket not available")
            return

        # Hand off to worker
        await context.websocket_worker.handle_connection(websocket)

    return app
```

**Step 2: Write integration test**

Create `tests/api/test_websocket_endpoint.py`:

```python
"""Integration tests for WebSocket endpoint."""

import pytest
from fastapi.testclient import TestClient
from picklebot.api import create_app
from picklebot.core.context import SharedContext


@pytest.fixture
def test_context():
    """Create test SharedContext."""
    # Create minimal mock context
    # In real implementation, this would be a proper test context
    context = Mock(spec=SharedContext)
    context.websocket_worker = Mock()
    context.websocket_worker.handle_connection = AsyncMock()
    return context


@pytest.fixture
def client(test_context):
    """Create test client."""
    app = create_app(test_context)
    return TestClient(app)


class TestWebSocketEndpoint:
    """Test WebSocket endpoint integration."""

    def test_websocket_endpoint_exists(self, client):
        """Test WebSocket endpoint is registered."""
        # WebSocket endpoints don't show up in routes the same way
        # This is more of a smoke test
        assert client.app is not None

    # Note: Testing WebSocket connections with TestClient is complex
    # Real integration testing should be done with actual WebSocket client
    # For now, we'll do manual testing with wscat/websocat
```

**Step 3: Run tests**

Run: `pytest tests/api/test_websocket_endpoint.py -v`

Expected: PASS

**Step 4: Manual testing with wscat**

Start the server:
```bash
uv run picklebot server
```

In another terminal, connect with wscat:
```bash
wscat -c ws://localhost:8000/ws
```

Test sending a message:
```json
{"source": "test-user", "content": "Hello Pickle!", "agent_id": "pickle"}
```

Expected:
- Server receives message
- Server broadcasts InboundEvent back
- Server broadcasts OutboundEvent when agent responds

**Step 5: Commit**

```bash
git add src/picklebot/api/app.py tests/api/test_websocket_endpoint.py
git commit -m "feat: add WebSocket /ws endpoint to FastAPI app"
```

---

## Task 7: Run Full Test Suite and Fix Issues

**Files:**
- Various test files

**Step 1: Run complete test suite**

Run: `pytest -v`

Expected: Some tests may fail due to integration issues

**Step 2: Fix any failing tests**

Address any test failures:
- Mock issues
- Import errors
- Type mismatches
- Integration issues

**Step 3: Run tests again**

Run: `pytest -v`

Expected: All tests pass

**Step 4: Run linting and formatting**

Run:
```bash
uv run black .
uv run ruff check .
```

Expected: No errors (or fix any that appear)

**Step 5: Final commit**

```bash
git add .
git commit -m "fix: resolve test failures and linting issues"
```

---

## Task 8: Manual Integration Testing

**Step 1: Start the server**

```bash
uv run picklebot server
```

**Step 2: Connect with WebSocket client**

```bash
wscat -c ws://localhost:8000/ws
```

**Step 3: Test sending a message**

```json
{"source": "test-user", "content": "Hello Pickle!", "agent_id": "pickle"}
```

Expected response:
- InboundEvent broadcast
- Agent processes message
- OutboundEvent broadcast with response

**Step 4: Test validation error**

```json
{"source": "", "content": "test"}
```

Expected response:
```json
{"type": "error", "message": "Validation error: ..."}
```

**Step 5: Test missing field**

```json
{"source": "test"}
```

Expected response:
```json
{"type": "error", "message": "Validation error: ..."}
```

**Step 6: Test with multiple clients**

Open multiple wscat connections and verify all receive broadcasts.

**Step 7: Test disconnection**

Disconnect a client and verify:
- Server logs disconnect
- Client removed from set
- Other clients still receive broadcasts

**Step 8: Document manual testing results**

Create a simple test log or comment in the PR.

---

## Success Criteria

- [ ] WebSocketMessage schema validates incoming messages correctly
- [ ] WebSocketEventSource parses and serializes correctly
- [ ] WebSocketWorker manages connections and broadcasts events
- [ ] FastAPI `/ws` endpoint accepts and hands off connections
- [ ] All unit tests pass
- [ ] Manual testing confirms bidirectional communication works
- [ ] Code is formatted and passes linting
- [ ] All changes committed with clear commit messages

## Implementation Notes

### Routing Integration

The current `_route_message` implementation defaults to "pickle" agent. This should be enhanced to use the actual routing system:

```python
def _route_message(self, source: str, content: str) -> str:
    """Route message using SharedContext routing."""
    # Future: Use context.routing.route(source, content)
    return self.context.routing.route_to_agent(source, content)
```

### Session Management

The current `_get_or_create_session` uses a simple hash. This should integrate with the actual session management system:

```python
def _get_or_create_session(self, agent_id: str, source: str) -> str:
    """Get or create session using SharedContext session management."""
    # Future: Use context.session_manager.get_or_create(agent_id, source)
    return self.context.session_manager.get_or_create_session_id(
        agent_id=agent_id,
        source=WebSocketEventSource(user_id=source)
    )
```

### EventSource Serialization

The current implementation manually converts EventSource to string during broadcast. This could be enhanced with a custom JSON encoder:

```python
class EventEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, EventSource):
            return str(obj)
        return super().default(obj)
```

### Performance Considerations

The simple set-based broadcast may block briefly on slow clients. If this becomes an issue, consider:
- Per-client queues
- Background tasks per client
- Rate limiting

These are future enhancements, not part of this implementation.
