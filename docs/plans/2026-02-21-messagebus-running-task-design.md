# MessageBus Running Task Design

**Date:** 2026-02-21
**Status:** Approved

## Problem

The `MessageBus.start()` method doesn't return a task representing its running state. This causes the `MessageBusWorker` to complete immediately after calling `start()`, leading the server to think the worker crashed and restart it repeatedly.

```python
# Current behavior in MessageBusWorker
bus_tasks = [bus.start(callback) for bus in self.buses]
await asyncio.gather(*bus_tasks)  # Completes immediately since start() returns None
```

## Solution

Make `start()` return an `asyncio.Task` that runs until the bus stops. The task should:
- Complete normally when `stop()` is called
- Raise an exception if the bus crashes unexpectedly (fail-fast)

## Design

### Base Class Change

```python
class MessageBus(ABC, Generic[T]):
    @abstractmethod
    async def start(self, on_message: Callable[[str, T], Awaitable[None]]) -> asyncio.Task | None:
        """
        Start listening for messages.

        Returns:
            Task that runs until stop() is called, or None if already started.
        """
        pass
```

### TelegramBus Implementation

**New attributes:**
- `_running_task: asyncio.Task | None` - The running task
- `_stop_event: asyncio.Event` - Signal to stop the task

**start() method:**
```python
async def start(self, on_message) -> asyncio.Task | None:
    # Idempotent: return existing task if already started
    if self.application is not None:
        return self._running_task

    # ... setup application ...

    self._stop_event = asyncio.Event()

    async def run_until_stopped():
        """Run updater and monitor for unexpected stops."""
        await self.application.updater.start_polling()

        while self.application.updater.running:
            if self._stop_event.is_set():
                return  # Graceful stop
            await asyncio.sleep(1)

        # If we exit the loop without stop being called, it crashed
        if not self._stop_event.is_set():
            raise RuntimeError("Telegram updater stopped unexpectedly")

    self._running_task = asyncio.create_task(run_until_stopped())
    return self._running_task
```

**stop() method:**
```python
async def stop(self) -> None:
    if self.application is None:
        return

    # Signal the running task to stop
    self._stop_event.set()

    # Stop the updater
    if self.application.updater and self.application.updater.running:
        await self.application.updater.stop()

    await self.application.stop()
    await self.application.shutdown()

    # Wait for running task to complete
    if self._running_task:
        try:
            await self._running_task
        except Exception:
            pass  # Task may have already failed

    self.application = None
    self._running_task = None
    self._stop_event = None
```

### DiscordBus Implementation

**New attribute:**
- `_running_task: asyncio.Task | None` - The running task

**start() method:**
```python
async def start(self, on_message) -> asyncio.Task | None:
    if self.client is not None:
        return self._running_task

    # ... setup client ...

    self._running_task = asyncio.create_task(self.client.start(self.config.bot_token))

    # Wait a moment for client to initialize
    await asyncio.sleep(0.5)

    return self._running_task
```

**stop() method:**
```python
async def stop(self) -> None:
    if self.client is None:
        return

    await self.client.close()

    # Wait for running task to complete
    if self._running_task:
        try:
            await self._running_task
        except Exception:
            pass  # Task may have already failed

    self.client = None
    self._running_task = None
```

## Error Handling

**Fail-fast approach:** If any bus task raises an exception, `asyncio.gather()` will propagate it, causing the `MessageBusWorker` to crash. The server's restart mechanism will then restart the worker.

| Scenario | Behavior |
|----------|----------|
| Startup fails | Task raises → worker crashes → server restarts |
| Runtime crash | Task raises → worker crashes → server restarts |
| Graceful stop | `stop()` sets event → task completes normally |

## Files Changed

- `src/picklebot/messagebus/base.py` - Update return type annotation
- `src/picklebot/messagebus/telegram_bus.py` - Implement task return
- `src/picklebot/messagebus/discord_bus.py` - Implement task return

## Testing

- Test that `start()` returns a task
- Test that task completes when `stop()` is called
- Test that task raises if bus crashes (mock a crash)
- Test idempotent behavior (calling start() twice returns same task)
