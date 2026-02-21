# Idempotent MessageBus Start/Stop Design

**Date:** 2026-02-21
**Status:** Approved

## Problem

The `MessageBus` implementations (`TelegramBus`, `DiscordBus`) do not have idempotent `start()` and `stop()` methods. Calling these methods multiple times or in the wrong state can cause issues, especially when workers are restarted after crashes.

## Solution

Make `start()` and `stop()` idempotent by using the existing `application`/`client` attributes as state indicators.

## Design

### Approach

Use existing attributes to track state:
- **TelegramBus**: `self.application` (None = not started, not None = started)
- **DiscordBus**: `self.client` (None = not started, not None = started)

No new attributes needed.

### TelegramBus Changes

```python
async def start(self, on_message):
    if self.application is not None:
        logger.debug("TelegramBus already started, skipping")
        return
    # ... existing start logic ...

async def stop(self):
    if self.application is None:
        logger.debug("TelegramBus not running, skipping stop")
        return
    # ... existing stop logic ...
    self.application = None  # Reset to allow restart
```

### DiscordBus Changes

```python
async def start(self, on_message):
    if self.client is not None:
        logger.debug("DiscordBus already started, skipping")
        return
    # ... existing start logic ...

async def stop(self):
    if self.client is None:
        logger.debug("DiscordBus not running, skipping stop")
        return
    # ... existing stop logic ...
    self.client = None  # Reset to allow restart
```

## Behavior

| Call Sequence | Before | After |
|---------------|--------|-------|
| `start()` once | Starts bus | Starts bus |
| `start()` twice | Might fail/recreate | No-op on second call |
| `stop()` once | Stops bus | Stops bus |
| `stop()` twice | Might error | No-op on second call |
| `stop()` without `start()` | Might error | No-op |
| `start()` → `stop()` → `start()` | Might fail | Works cleanly |

## Files Changed

- `src/picklebot/messagebus/telegram_bus.py`
- `src/picklebot/messagebus/discord_bus.py`

## Testing

Manual testing:
1. Start server, verify buses start once
2. Restart worker (simulate crash), verify no errors
3. Stop and start server multiple times, verify clean behavior
