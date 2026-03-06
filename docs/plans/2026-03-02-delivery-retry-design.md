# Delivery Worker Retry Logic

## Summary

Add proper retry logic to `DeliveryWorker` using in-place retries with exponential backoff. When `bus.reply()` fails, wait with jitter, then retry all chunks. After `MAX_RETRIES`, log and ack (drop the message).

## Context

The `delivery_worker.py` had defined `BACKOFF_MS`, `compute_backoff_ms()`, and `MAX_RETRIES` but never used them. Failed deliveries would just log an error with no retry.

## Design Decisions

1. **In-place retry with sleep** - Use `asyncio.sleep(backoff)` within the same handler (simpler than republishing)
2. **Log and drop after max retries** - After 5 failures, log error and ack the event
3. **Retry all chunks together** - If any chunk fails, retry the entire message from scratch

## Changes to `delivery_worker.py`

### 1. Add `asyncio` import

```python
import asyncio
```

### 2. New method `_deliver_with_retry()`

```python
async def _deliver_with_retry(
    self, chunks: list[str], source: EventSource, bus: "Channel[Any]"
) -> bool:
    """Deliver all chunks with retry logic. Returns True on success."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            for chunk in chunks:
                await bus.reply(chunk, source)
            return True
        except Exception as e:
            if attempt < MAX_RETRIES:
                backoff_ms = compute_backoff_ms(attempt)
                self.logger.warning(
                    f"Delivery failed (attempt {attempt}/{MAX_RETRIES}), "
                    f"retrying in {backoff_ms}ms: {e}"
                )
                await asyncio.sleep(backoff_ms / 1000)
            else:
                self.logger.error(f"Delivery failed after {MAX_RETRIES} attempts: {e}")
                return False
    return False
```

### 3. Simplify `handle_event()`

Replace the inner delivery loop with a call to `_deliver_with_retry()`.

## Behavior Summary

| Scenario | Behavior |
|----------|----------|
| First attempt succeeds | Ack immediately |
| Attempt 1-4 fails | Log warning, sleep with backoff, retry all chunks |
| Attempt 5 fails | Log error, ack (drop message) |
| Any chunk fails | Retry all chunks from scratch |

## Backoff Schedule

Defined in `BACKOFF_MS`: 5s, 25s, 2min, 10min (with ±20% jitter)
