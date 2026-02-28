# Unified Worker Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify all workers under a consistent pattern with lifecycle management and auto-subscription.

**Architecture:** Move `utils/worker.py` to `server/worker.py`, add `SubscriberWorker` base class, convert `AgentDispatcher`, `DeliveryWorker`, and `WebSocketWorker` to extend `SubscriberWorker` with auto-subscription in `__init__`.

**Tech Stack:** Python asyncio, pytest

---

## Task 1: Move Worker Base Class

**Files:**
- Create: `src/picklebot/server/worker.py`
- Modify: `src/picklebot/server/base.py`
- Delete: `src/picklebot/utils/worker.py`

**Step 1: Create server/worker.py with Worker class**

Move the content from `utils/worker.py` to `server/worker.py`:

```python
# src/picklebot/server/worker.py
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


class SubscriberWorker(Worker):
    """Worker that only subscribes to events, no active loop."""

    async def run(self) -> None:
        """Wait for cancellation - actual work happens in event handlers."""
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
```

**Step 2: Update server/base.py to import from new location**

```python
# src/picklebot/server/base.py
"""Base classes for worker architecture."""

from picklebot.server.worker import Worker, SubscriberWorker

__all__ = ["Worker", "SubscriberWorker"]
```

**Step 3: Update server/__init__.py exports**

```python
# src/picklebot/server/__init__.py
"""Server module - workers and orchestrator."""

from picklebot.server.base import Worker, SubscriberWorker
from picklebot.server.server import Server
from picklebot.server.agent_worker import AgentDispatcher  # Will rename in next task
from picklebot.server.cron_worker import CronWorker
from picklebot.server.messagebus_worker import MessageBusWorker

__all__ = [
    "Worker",
    "SubscriberWorker",
    "Server",
    "AgentDispatcher",
    "CronWorker",
    "MessageBusWorker",
]
```

**Step 4: Delete old utils/worker.py**

```bash
rm src/picklebot/utils/worker.py
```

**Step 5: Run tests to verify nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: move Worker to server module, add SubscriberWorker"
```

---

## Task 2: Convert AgentDispatcher to AgentWorker

**Files:**
- Modify: `src/picklebot/server/agent_worker.py`
- Modify: `src/picklebot/server/server.py`
- Modify: `src/picklebot/cli/chat.py`
- Modify: `src/picklebot/server/__init__.py`

**Step 1: Rename class and extend SubscriberWorker**

Update `src/picklebot/server/agent_worker.py`:

```python
# src/picklebot/server/agent_worker.py
"""Agent worker for executing agent jobs."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from picklebot.server.base import SubscriberWorker
from picklebot.core.agent import Agent, SessionMode
from picklebot.events.types import Event, EventType, Source
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.core.agent_loader import AgentDef


# Maximum number of retry attempts for failed sessions
MAX_RETRIES = 3

logger = logging.getLogger(__name__)


class SessionExecutor:
    """Executes a single agent session from an event."""

    def __init__(
        self,
        context: "SharedContext",
        agent_def: "AgentDef",
        event: Event,
        semaphore: asyncio.Semaphore,
    ):
        self.context = context
        self.agent_def = agent_def
        self.event = event
        self.semaphore = semaphore

        # Extract fields from event (with defaults)
        metadata = event.metadata or {}
        self.job_id = metadata.get("job_id", event.session_id)
        self.agent_id = metadata.get("agent_id", "")
        self.mode = SessionMode(metadata.get("mode", "CHAT"))
        self.retry_count = metadata.get("retry_count", 0)

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
                    session = agent.new_session(self.mode, session_id=session_id)
            else:
                session = agent.new_session(self.mode)
                session_id = session.session_id

            response = await session.chat(self.event.content)
            logger.info(f"Session completed: {session_id}")

            # Publish RESULT event for dispatch callers
            result_event = Event(
                type=EventType.DISPATCH_RESULT if self.event.type == EventType.DISPATCH else EventType.OUTBOUND,
                session_id=session_id,
                content=response,
                source=Source.agent(self.agent_def.id),
                timestamp=time.time(),
                metadata={"job_id": self.job_id},
            )
            await self.context.eventbus.publish(result_event)

        except Exception as e:
            logger.error(f"Session failed: {e}")

            if self.retry_count < MAX_RETRIES:
                self.event.metadata["retry_count"] = self.retry_count + 1
                self.event.content = "."  # Minimal message for retry
                await self.context.eventbus.publish(self.event)
            else:
                # Publish RESULT event with error for dispatch callers
                result_event = Event(
                    type=EventType.DISPATCH_RESULT if self.event.type == EventType.DISPATCH else EventType.OUTBOUND,
                    session_id=session_id,
                    content="",
                    source=Source.agent(self.agent_def.id),
                    timestamp=time.time(),
                    metadata={"job_id": self.job_id, "error": str(e)},
                )
                await self.context.eventbus.publish(result_event)


class AgentWorker(SubscriberWorker):
    """Dispatches events to session executors with per-agent concurrency control.

    Auto-subscribes to:
    - INBOUND events (from platforms, cron, retries)
    - DISPATCH events (from subagent calls)
    """

    CLEANUP_THRESHOLD = 5

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self._semaphores: dict[str, asyncio.Semaphore] = {}

        # Auto-subscribe to events
        self.context.eventbus.subscribe(EventType.INBOUND, self.handle_inbound)
        self.context.eventbus.subscribe(EventType.DISPATCH, self.handle_dispatch)
        self.logger.info("AgentWorker subscribed to INBOUND and DISPATCH events")

    async def handle_inbound(self, event: Event) -> None:
        """Handle INBOUND event (from platforms, cron, retries)."""
        if event.type != EventType.INBOUND:
            return

        # Ensure agent_id is set (use default if not in metadata)
        metadata = event.metadata or {}
        if "agent_id" not in metadata:
            # Mutate event to include default agent_id
            event.metadata = {**metadata, "agent_id": self.context.config.default_agent}

        await self._dispatch_event(event)
        self.logger.debug(
            f"Dispatched job for INBOUND event, job_id={metadata.get('job_id')}"
        )

    async def handle_dispatch(self, event: Event) -> None:
        """Handle DISPATCH event (from subagent calls)."""
        if event.type != EventType.DISPATCH:
            return

        await self._dispatch_event(event)
        metadata = event.metadata or {}
        self.logger.debug(
            f"Dispatched job for DISPATCH event, job_id={metadata.get('job_id')}"
        )

    async def _dispatch_event(self, event: Event) -> None:
        """Create executor task for event."""
        metadata = event.metadata or {}
        agent_id = metadata.get("agent_id", self.context.config.default_agent)

        try:
            agent_def = self.context.agent_loader.load(agent_id)
        except DefNotFoundError as e:
            logger.error(f"Agent not found: {agent_id}: {e}")
            job_id = (event.metadata or {}).get("job_id", event.session_id)
            result_event = Event(
                type=EventType.DISPATCH_RESULT if event.type == EventType.DISPATCH else EventType.OUTBOUND,
                session_id=event.session_id,
                content="",
                source="agent:dispatcher",
                timestamp=time.time(),
                metadata={
                    "job_id": job_id,
                    "error": str(e),
                },
            )
            await self.context.eventbus.publish(result_event)
            return

        sem = self._get_or_create_semaphore(agent_def)
        asyncio.create_task(SessionExecutor(self.context, agent_def, event, sem).run())
        self._maybe_cleanup_semaphores()

    def _get_or_create_semaphore(self, agent_def: "AgentDef") -> asyncio.Semaphore:
        """Get existing or create new semaphore for agent."""
        if agent_def.id not in self._semaphores:
            self._semaphores[agent_def.id] = asyncio.Semaphore(
                agent_def.max_concurrency
            )
            self.logger.debug(
                f"Created semaphore for {agent_def.id} with value {agent_def.max_concurrency}"
            )
        return self._semaphores[agent_def.id]

    def _maybe_cleanup_semaphores(self) -> None:
        """Remove semaphores for deleted agents."""
        if len(self._semaphores) <= self.CLEANUP_THRESHOLD:
            return

        existing = {a.id for a in self.context.agent_loader.discover_agents()}
        stale = set(self._semaphores.keys()) - existing
        for agent_id in stale:
            del self._semaphores[agent_id]
            self.logger.debug(f"Cleaned up semaphore for deleted agent: {agent_id}")


# Backward compatibility alias
AgentDispatcher = AgentWorker
```

**Step 2: Update server/server.py imports and usage**

The import line changes from:
```python
from picklebot.server.agent_worker import AgentDispatcher
```
to:
```python
from picklebot.server.agent_worker import AgentWorker
```

And in `_setup_workers()`:
```python
agent_dispatcher = AgentDispatcher(self.context)
agent_dispatcher.subscribe()
```
becomes:
```python
AgentWorker(self.context),
```

**Step 3: Update cli/chat.py imports**

Change:
```python
from picklebot.server.agent_worker import AgentDispatcher
```
to:
```python
from picklebot.server.agent_worker import AgentWorker
```

And:
```python
self.dispatcher = AgentDispatcher(self.context)
```
to:
```python
AgentWorker(self.context),
```

**Step 4: Update server/__init__.py**

Change export from `AgentDispatcher` to `AgentWorker`:
```python
from picklebot.server.agent_worker import AgentWorker

__all__ = [
    # ...
    "AgentWorker",
    # ...
]
```

**Step 5: Run tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename AgentDispatcher to AgentWorker, extend SubscriberWorker"
```

---

## Task 3: Move and Convert DeliveryWorker

**Files:**
- Create: `src/picklebot/server/delivery_worker.py`
- Modify: `src/picklebot/server/server.py`
- Modify: `src/picklebot/cli/chat.py`
- Modify: `src/picklebot/server/__init__.py`
- Delete: `src/picklebot/events/delivery.py`

**Step 1: Create server/delivery_worker.py**

```python
# src/picklebot/server/delivery_worker.py
"""Delivery worker for outbound messages."""

import logging
import random
from typing import TYPE_CHECKING, Any

from picklebot.server.base import SubscriberWorker
from picklebot.events.types import Event, EventType

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.messagebus.base import MessageBus

logger = logging.getLogger(__name__)

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


class DeliveryWorker(SubscriberWorker):
    """Delivers OUTBOUND messages to platforms.

    Auto-subscribes to OUTBOUND events.
    """

    def __init__(self, context: "SharedContext"):
        super().__init__(context)

        # Auto-subscribe
        self.context.eventbus.subscribe(EventType.OUTBOUND, self.handle_event)
        self.logger.info("DeliveryWorker subscribed to OUTBOUND events")

    async def handle_event(self, event: Event) -> None:
        """Handle an outbound message event."""
        if event.type != EventType.OUTBOUND:
            return

        try:
            # Look up where to deliver
            platform_info = self._lookup_platform(event.session_id, event.metadata)
            platform = platform_info["platform"]

            # Get limit and chunk
            limit = PLATFORM_LIMITS.get(platform, float("inf"))
            if limit != float("inf"):
                limit = int(limit)
            chunks = chunk_message(
                event.content,
                int(limit) if limit != float("inf") else len(event.content),
            )

            # Deliver each chunk
            for chunk in chunks:
                await self._deliver(platform, platform_info, chunk)

            # Ack the event
            self.context.eventbus.ack(event)

            self.logger.info(
                f"Delivered message to {platform} for session {event.session_id}"
            )

        except Exception as e:
            self.logger.error(f"Failed to deliver message: {e}")
            # TODO: Retry logic with backoff

    def _lookup_platform(
        self, session_id: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Look up platform and delivery context for a session.

        Args:
            session_id: Session ID to look up (UUID format)
            metadata: Optional event metadata (may contain 'platform' for proactive msgs)

        Returns:
            Dict with platform info (platform, user_id, chat_id/channel_id)
        """
        # Check metadata for platform (proactive messages from tools)
        if metadata and "platform" in metadata:
            platform = metadata["platform"]
            return self._get_proactive_platform_info(platform)

        # Look in messagebus config for session -> platform mapping
        messagebus_config = self.context.config.messagebus

        # Check Telegram sessions
        if messagebus_config.telegram:
            sessions = messagebus_config.telegram.sessions
            for user_id, sess_id in sessions.items():
                if sess_id == session_id:
                    return {
                        "platform": "telegram",
                        "user_id": user_id,
                        "chat_id": messagebus_config.telegram.default_chat_id,
                    }

        # Check Discord sessions
        if messagebus_config.discord:
            sessions = messagebus_config.discord.sessions
            for user_id, sess_id in sessions.items():
                if sess_id == session_id:
                    return {
                        "platform": "discord",
                        "user_id": user_id,
                        "channel_id": messagebus_config.discord.default_chat_id,
                    }

        # Default to CLI if not found
        return {"platform": "cli"}

    def _get_proactive_platform_info(self, platform: str) -> dict[str, Any]:
        """Get platform info for proactive messages.

        Args:
            platform: Target platform name

        Returns:
            Dict with platform info for proactive delivery
        """
        messagebus_config = self.context.config.messagebus

        if platform == "telegram" and messagebus_config.telegram:
            return {
                "platform": "telegram",
                "chat_id": messagebus_config.telegram.default_chat_id,
            }
        elif platform == "discord" and messagebus_config.discord:
            return {
                "platform": "discord",
                "channel_id": messagebus_config.discord.default_chat_id,
            }

        # Default to CLI for unknown platforms
        return {"platform": "cli"}

    def _get_bus(self, platform: str) -> "MessageBus[Any] | None":
        """Get the message bus for a platform."""
        for bus in self.context.messagebus_buses:
            if bus.platform_name == platform:
                return bus
        return None

    async def _deliver(
        self, platform: str, platform_info: dict[str, Any], content: str
    ) -> None:
        """Deliver a message chunk to a platform."""
        bus = self._get_bus(platform)

        if platform == "telegram" and bus is not None:
            # Import here to avoid circular dependency
            from picklebot.messagebus.telegram_bus import TelegramContext

            chat_id = platform_info.get("chat_id")
            user_id = platform_info.get("user_id")
            if chat_id and user_id:
                ctx = TelegramContext(user_id=user_id, chat_id=chat_id)
                await bus.reply(content, ctx)
            elif chat_id:
                # Use post for proactive message to default chat
                await bus.post(content)

        elif platform == "discord" and bus is not None:
            # Import here to avoid circular dependency
            from picklebot.messagebus.discord_bus import DiscordContext

            channel_id = platform_info.get("channel_id")
            user_id = platform_info.get("user_id")
            if channel_id and user_id:
                ctx = DiscordContext(user_id=user_id, channel_id=channel_id)
                await bus.reply(content, ctx)
            elif channel_id:
                # Use post for proactive message to default channel
                await bus.post(content)

        elif platform == "cli":
            # CLI just prints to stdout
            print(content)
```

**Step 2: Update server/server.py**

Change import from:
```python
from picklebot.events.delivery import DeliveryWorker
```
to:
```python
from picklebot.server.delivery_worker import DeliveryWorker
```

In `_setup_workers()`:
```python
delivery_worker = DeliveryWorker(self.context)
delivery_worker.subscribe(self.context.eventbus)
self.workers.append(CronWorker(self.context))
```
becomes:
```python
DeliveryWorker(self.context),
CronWorker(self.context),
```

**Step 3: Update cli/chat.py**

Change import from:
```python
from picklebot.events.delivery import DeliveryWorker
```
to:
```python
from picklebot.server.delivery_worker import DeliveryWorker
```

And remove the subscribe call.

**Step 4: Update server/__init__.py**

Add export:
```python
from picklebot.server.delivery_worker import DeliveryWorker

__all__ = [
    # ...
    "DeliveryWorker",
    # ...
]
```

**Step 5: Delete old file**

```bash
rm src/picklebot/events/delivery.py
```

**Step 6: Run tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor: move DeliveryWorker to server module, extend SubscriberWorker"
```

---

## Task 4: Move and Convert WebSocketWorker

**Files:**
- Create: `src/picklebot/server/websocket_worker.py`
- Modify: `src/picklebot/server/__init__.py`
- Delete: `src/picklebot/events/websocket.py`

**Step 1: Create server/websocket_worker.py**

```python
# src/picklebot/server/websocket_worker.py
"""WebSocket worker for broadcasting events to connected clients."""

import logging
from typing import TYPE_CHECKING

from picklebot.server.base import SubscriberWorker
from picklebot.events.types import Event, EventType

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class WebSocketWorker(SubscriberWorker):
    """Broadcasts events to WebSocket clients.

    Auto-subscribes to ALL event types.
    """

    def __init__(self, context: "SharedContext"):
        super().__init__(context)
        self._clients: set = set()  # Future: set of WebSocket connections

        # Auto-subscribe to all event types
        for event_type in EventType:
            self.context.eventbus.subscribe(event_type, self.handle_event)
        self.logger.info(f"WebSocketWorker subscribed to all {len(EventType)} event types")

    async def handle_event(self, event: Event) -> None:
        """Handle an event by broadcasting to WebSocket clients.

        TODO: Implement actual WebSocket broadcasting.
        For now, just logs the event.
        """
        self.logger.debug(f"WebSocket stub received {event.type.value} event")
```

**Step 2: Update server/__init__.py**

Add export:
```python
from picklebot.server.websocket_worker import WebSocketWorker

__all__ = [
    # ...
    "WebSocketWorker",
]
```

**Step 3: Delete old file**

```bash
rm src/picklebot/events/websocket.py
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move WebSocketWorker to server module, extend SubscriberWorker"
```

---

## Task 5: Simplify Server Worker Setup

**Files:**
- Modify: `src/picklebot/server/server.py`

**Step 1: Refactor _setup_workers()**

```python
# src/picklebot/server/server.py
"""Server orchestrator for worker-based architecture."""

import asyncio
import logging
from typing import TYPE_CHECKING

import uvicorn

from picklebot.server.base import Worker
from picklebot.server.agent_worker import AgentWorker
from picklebot.server.cron_worker import CronWorker
from picklebot.server.delivery_worker import DeliveryWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.server.websocket_worker import WebSocketWorker
from picklebot.utils.config import ConfigReloader
from picklebot.api import create_app

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext

logger = logging.getLogger(__name__)


class Server:
    """Orchestrates workers with queue-based communication."""

    def __init__(self, context: "SharedContext"):
        self.context = context
        self.workers: list[Worker] = []
        self._api_task: asyncio.Task | None = None
        self.config_reloader: ConfigReloader = ConfigReloader(self.context.config)

    async def run(self) -> None:
        """Start all workers and monitor for crashes."""
        self._setup_workers()
        self._start_workers()

        if self.context.config.api:
            self._api_task = asyncio.create_task(self._run_api())

        try:
            await self._monitor_workers()
        except asyncio.CancelledError:
            logger.info("Server shutting down...")
            await self._stop_all()
            raise

    def _setup_workers(self) -> None:
        """Create all workers."""
        self.config_reloader.start()

        # All workers created uniformly - subscriptions happen in __init__
        self.workers = [
            self.context.eventbus,      # EventBus (active worker)
            AgentWorker(self.context),  # SubscriberWorker
            CronWorker(self.context),   # Active worker
            DeliveryWorker(self.context),   # SubscriberWorker
            WebSocketWorker(self.context),  # SubscriberWorker
        ]

        logger.info(f"Server setup complete with {len(self.workers)} core workers")

        # MessageBusWorker only if enabled
        if self.context.config.messagebus.enabled:
            buses = self.context.messagebus_buses
            if buses:
                self.workers.append(MessageBusWorker(self.context))
                logger.info(f"MessageBus enabled with {len(buses)} bus(es)")
            else:
                logger.warning("MessageBus enabled but no buses configured")

    def _start_workers(self) -> None:
        """Start all workers as tasks."""
        for worker in self.workers:
            worker.start()
            logger.info(f"Started {worker.__class__.__name__}")

    async def _monitor_workers(self) -> None:
        """Monitor worker tasks, restart on crash."""
        while True:
            for worker in self.workers:
                if worker.has_crashed():
                    exc = worker.get_exception()
                    if exc is None:
                        logger.warning(
                            f"{worker.__class__.__name__} exited unexpectedly"
                        )
                    else:
                        logger.error(f"{worker.__class__.__name__} crashed: {exc}")

                    worker.start()
                    logger.info(f"Restarted {worker.__class__.__name__}")

            await asyncio.sleep(5)

    async def _stop_all(self) -> None:
        """Stop all workers gracefully."""
        for worker in self.workers:
            await worker.stop()

        # Stop config reloader
        if self.config_reloader is not None:
            self.config_reloader.stop()

    async def _run_api(self) -> None:
        """Run the HTTP API server."""
        if not self.context.config.api:
            return

        app = create_app(self.context)
        config = uvicorn.Config(
            app,
            host=self.context.config.api.host,
            port=self.context.config.api.port,
        )
        server = uvicorn.Server(config)
        logger.info(
            f"API server started on {self.context.config.api.host}:{self.context.config.api.port}"
        )
        await server.serve()
```

**Step 2: Run tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: simplify Server worker setup with uniform pattern"
```

---

## Task 6: Simplify CLI Chat Setup

**Files:**
- Modify: `src/picklebot/cli/chat.py`

**Step 1: Refactor ChatLoop to match Server pattern**

```python
# src/picklebot/cli/chat.py
"""Chat CLI command for interactive sessions."""

import asyncio
import logging

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from picklebot.core.context import SharedContext
from picklebot.messagebus.cli_bus import CliBus
from picklebot.server.base import Worker
from picklebot.server.agent_worker import AgentWorker
from picklebot.server.delivery_worker import DeliveryWorker
from picklebot.server.messagebus_worker import MessageBusWorker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class ChatLoop:
    """Interactive chat session using event-driven architecture."""

    def __init__(self, config: Config):
        self.config = config
        self.console = Console()

        # Create CliBus and SharedContext
        self.bus = CliBus()
        self.context = SharedContext(config=config, buses=[self.bus])

        # Create ALL workers - same pattern as Server
        self.workers: list[Worker] = [
            self.context.eventbus,
            AgentWorker(self.context),
            DeliveryWorker(self.context),
            MessageBusWorker(self.context),
        ]

    async def run(self) -> None:
        """Run the interactive chat loop."""
        # Display welcome message
        self.console.print(
            Panel(
                Text("Welcome to pickle-bot!", style="bold cyan"),
                title="Pickle",
                border_style="cyan",
            )
        )
        self.console.print("Type 'quit' or 'exit' to end the session.\n")

        # Start all workers
        for worker in self.workers:
            worker.start()

        try:
            # Wait forever - workers handle everything
            await asyncio.Future()
        except asyncio.CancelledError:
            self.console.print("\nGoodbye!")
            # Stop all workers gracefully
            for worker in self.workers:
                await worker.stop()
            raise


def chat_command(ctx: typer.Context) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config)
    asyncio.run(chat_loop.run())
```

**Step 2: Run tests**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add -A
git commit -m "refactor: simplify CLI ChatLoop to match Server pattern"
```

---

## Task 7: Final Cleanup and Verification

**Files:**
- Modify: `src/picklebot/events/__init__.py` (if needed)
- Any remaining import updates

**Step 1: Check for any remaining imports of old modules**

Run: `grep -r "from picklebot.events.delivery" src/`
Run: `grep -r "from picklebot.events.websocket" src/`
Run: `grep -r "from picklebot.utils.worker" src/`
Run: `grep -r "AgentDispatcher" src/` (should only find backward compat alias)

Fix any remaining imports.

**Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 3: Run linting**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 4: Test CLI manually**

Run: `uv run picklebot chat`
Expected: Chat starts without errors

**Step 5: Final commit**

```bash
git add -A
git commit -m "refactor: complete unified worker architecture migration"
```

---

## Summary

After completion:
- All workers extend `Worker` or `SubscriberWorker`
- Auto-subscription in `__init__`
- Uniform lifecycle management
- Server and CLI use identical patterns
- Clean file organization in `server/` module
