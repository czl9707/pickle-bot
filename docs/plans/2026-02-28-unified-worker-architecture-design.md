# Unified Worker Architecture Design

**Date:** 2026-02-28

## Problem

Current worker/subscription architecture is inconsistent:

| Component | Extends Worker | Subscribe Signature |
|-----------|---------------|---------------------|
| EventBus | Yes | N/A (IS the bus) |
| CronWorker | Yes | N/A (publisher only) |
| MessageBusWorker | Yes | N/A (publisher only) |
| AgentDispatcher | No | `subscribe()` (no params) |
| DeliveryWorker | No | `subscribe(eventbus)` (takes param) |
| WebSocketWorker | No | `subscribe(eventbus)` (takes param) |

Issues:
- Some workers get lifecycle management (restart on crash), others don't
- Two different subscribe patterns
- Server setup has special cases for different worker types
- CLI and Server have different patterns

## Solution

Make everything a Worker with a consistent pattern.

### Worker Base Classes

```python
# server/worker.py

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

    def is_running(self) -> bool: ...
    def has_crashed(self) -> bool: ...
    def get_exception(self) -> BaseException | None: ...
    async def stop(self) -> None: ...


class SubscriberWorker(Worker):
    """Worker that only subscribes to events, no active loop."""

    async def run(self) -> None:
        """Wait for cancellation - actual work happens in event handlers."""
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            pass
```

### File Structure

```
server/
├── __init__.py
├── base.py              # Re-exports Worker, SubscriberWorker
├── worker.py            # Worker + SubscriberWorker (moved from utils/)
├── server.py            # Server orchestrator
├── agent_worker.py      # AgentWorker (renamed from AgentDispatcher)
├── cron_worker.py
├── messagebus_worker.py
├── delivery_worker.py   # Moved from events/delivery.py
└── websocket_worker.py  # Moved from events/websocket.py
```

### Worker Conversions

#### AgentWorker (formerly AgentDispatcher)

- Extends `SubscriberWorker`
- Auto-subscribes to `INBOUND` and `DISPATCH` in `__init__`
- Removes `subscribe()` and `unsubscribe()` methods

#### DeliveryWorker

- Extends `SubscriberWorker`
- Auto-subscribes to `OUTBOUND` in `__init__`
- Removes `subscribe()` method

#### WebSocketWorker

- Extends `SubscriberWorker`
- Auto-subscribes to ALL event types in `__init__`
- Removes `subscribe()` method

### Server Setup

```python
def _setup_workers(self) -> None:
    """Create all workers."""
    self.config_reloader.start()

    self.workers = [
        self.context.eventbus,
        AgentWorker(self.context),
        CronWorker(self.context),
        DeliveryWorker(self.context),
        WebSocketWorker(self.context),
    ]

    if self.context.config.messagebus.enabled:
        buses = self.context.messagebus_buses
        if buses:
            self.workers.append(MessageBusWorker(self.context))
```

### CLI Chat Setup

```python
def __init__(self, config: Config):
    # ...
    self.workers: list[Worker] = [
        self.context.eventbus,
        AgentWorker(self.context),
        DeliveryWorker(self.context),
        MessageBusWorker(self.context),
    ]

async def run(self) -> None:
    for worker in self.workers:
        worker.start()

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        for worker in self.workers:
            await worker.stop()
        raise
```

## Benefits

1. **Uniform interface** - All components implement `Worker`
2. **Lifecycle management** - All workers can be monitored/restarted
3. **Code simplification** - One pattern for all workers
4. **Consistency** - CLI and Server use identical patterns

## Migration Checklist

- [ ] Move `utils/worker.py` → `server/worker.py`
- [ ] Add `SubscriberWorker` to `server/worker.py`
- [ ] Update `server/base.py` import
- [ ] Convert `AgentDispatcher` → `AgentWorker` (extends SubscriberWorker)
- [ ] Move `events/delivery.py` → `server/delivery_worker.py` (extends SubscriberWorker)
- [ ] Move `events/websocket.py` → `server/websocket_worker.py` (extends SubscriberWorker)
- [ ] Update `server/server.py` to use uniform worker setup
- [ ] Update `cli/chat.py` to match Server pattern
- [ ] Update all imports
- [ ] Delete old files
