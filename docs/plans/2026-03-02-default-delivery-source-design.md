# Default Delivery Source

## Problem

When agents or cron jobs generate outbound messages, `DeliveryWorker` skips delivery because the source has no platform (e.g., `agent:pickle` or `cron:reminder`). The desired behavior is to deliver these messages to a default platform source.

## Solution

Store a global `default_delivery_source` in runtime config that is:
1. Auto-populated on the first non-CLI platform message
2. Used as fallback when delivering outbound messages from non-platform sources

## Design

### Storage

Config key: `default_delivery_source` stored via `config.set_runtime()`

```python
# Set
context.config.set_runtime("default_delivery_source", "telegram:user:123:chat:456")

# Get
default = context.config.default_delivery_source
```

### Auto-population (ChannelWorker)

When processing a platform message (non-CLI), set the default only if not already configured:

```python
def _create_callback(self, platform: str):
    async def callback(message: str, source: EventSource) -> None:
        # ... existing code ...

        # Set default delivery source only on first non-CLI platform message
        if source.is_platform and source.platform_name != "cli":
            if not self.context.config.default_delivery_source:
                self.context.config.set_runtime("default_delivery_source", str(source))

        # ... rest of callback ...

    return callback
```

### Delivery Fallback (DeliveryWorker)

When source has no platform, use the default:

```python
# Get platform name from source
platform = source.platform_name
if not platform:
    # Try default delivery source for agent/cron events
    default_source_str = self.context.config.default_delivery_source
    if default_source_str:
        try:
            source = EventSource.from_string(default_source_str)
            platform = source.platform_name
        except ValueError as e:
            self.logger.error(f"Invalid default_delivery_source: {e}")
            return
    else:
        self.logger.warning(
            f"No platform for session {event.session_id} and no default_delivery_source configured"
        )
        return
```

### Error Handling

1. **Invalid default_source string** - Log error and skip delivery
2. **Default source platform not available** - Existing `_get_bus()` returns `None`, nothing sent

## Testing

### test_channels_worker.py

1. First platform message sets `default_delivery_source`
2. CLI messages don't update the default
3. Subsequent platform messages don't overwrite existing default

### test_delivery_worker.py

1. OutboundEvent from agent delivers to configured default source
2. OutboundEvent from agent with no default skips with warning
3. OutboundEvent from platform source still delivers directly (existing behavior)

## Files Changed

| File | Change |
|------|--------|
| `channels_worker.py` | Set `default_delivery_source` on first non-CLI platform message |
| `delivery_worker.py` | Fallback to `default_delivery_source` when source has no platform |
| `test_channels_worker.py` | Tests for auto-population |
| `test_delivery_worker.py` | Tests for fallback delivery |
