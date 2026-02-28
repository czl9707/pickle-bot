# Typed Event System Design

## Problem

Two issues in the current event system:

1. **Event emission is inconsistent** - INBOUND should always respond with OUTBOUND, DISPATCH should always respond with DISPATCH_RESULT, and retries should requeue the original event with minimal content.

2. **Metadata is abused** - Loose `dict[str, Any]` leads to unclear contracts, typos, and scattered knowledge of what fields exist.

## Solution

Replace the single `Event` class with specialized typed event classes, each with explicit fields.

## Event Classes

```python
# core/events.py

from dataclasses import dataclass
from picklebot.messagebus.base import MessageContext

@dataclass
class InboundEvent:
    """External work entering the system (platforms, cron, retry)."""
    session_id: str
    agent_id: str
    source: str                     # "telegram:user_123", "cron:daily"
    content: str
    timestamp: float
    retry_count: int = 0
    context: MessageContext | None = None  # TelegramContext, DiscordContext, CliContext

@dataclass
class OutboundEvent:
    """Agent response to deliver to platforms."""
    session_id: str
    agent_id: str
    source: str                     # "agent:pickle"
    content: str
    timestamp: float
    error: str | None = None

@dataclass
class DispatchEvent:
    """Internal agent-to-agent delegation."""
    session_id: str                 # new session for subagent
    agent_id: str                   # target agent
    source: str                     # calling agent
    content: str
    timestamp: float
    retry_count: int = 0
    parent_session_id: str          # link back to caller's session

@dataclass
class DispatchResultEvent:
    """Result of a dispatched job."""
    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float
    error: str | None = None

# Type alias for all events
Event = InboundEvent | OutboundEvent | DispatchEvent | DispatchResultEvent
```

## Event Flow Rules

| Input Event | Success Output | Failure (retryable) | Failure (max retries) |
|-------------|----------------|---------------------|----------------------|
| `InboundEvent` | `OutboundEvent` (same session_id) | Requeue `InboundEvent` with `retry_count+1`, `content="."` | `OutboundEvent` with error |
| `DispatchEvent` | `DispatchResultEvent` (same session_id) | Requeue `DispatchEvent` with `retry_count+1`, `content="."` | `DispatchResultEvent` with error |

### Retry Logic

```python
MAX_RETRIES = 3

# On failure:
if event.retry_count < MAX_RETRIES:
    retry_event = dataclasses.replace(event, retry_count=event.retry_count + 1, content=".")
    await eventbus.publish(retry_event)
else:
    # Publish result with error
    result_event = OutboundEvent(...)  # or DispatchResultEvent
    await eventbus.publish(result_event)
```

## Migration Plan

### Files to Update

1. **`core/events.py`** - Replace `Event` class with typed variants, keep `EventType` enum for serialization
2. **`server/agent_worker.py`** - Update to use typed events and proper retry logic
3. **`server/messagebus_worker.py`** - Create `InboundEvent` with context
4. **`server/cron_worker.py`** - Create `InboundEvent`
5. **`tools/subagent_tool.py`** - Create `DispatchEvent`, handle `DispatchResultEvent`
6. **`tools/post_message_tool.py`** - Create `OutboundEvent`
7. **`server/delivery_worker.py`** - Handle `OutboundEvent`, use context for routing
8. **`core/eventbus.py`** - Update subscription to work with event types
9. **`events/bus.py`** - If exists, update similarly

### Serialization

Each event class needs `to_dict()` and `from_dict()` for persistence:

```python
def to_dict(self) -> dict[str, Any]:
    data = {...}
    if self.context:
        data["context"] = {
            "type": type(self.context).__name__,
            "data": dataclasses.asdict(self.context)
        }
    return data

@classmethod
def from_dict(cls, data: dict[str, Any]) -> "InboundEvent":
    # Deserialize context based on type
    ...
```

### EventType Enum (for serialization only)

```python
class EventType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    DISPATCH = "dispatch"
    DISPATCH_RESULT = "dispatch_result"
    STATUS = "status"  # Keep for future use
```

## Benefits

1. **Type safety** - IDE autocomplete, mypy checking
2. **Clear contracts** - Each event type has explicit fields
3. **Self-documenting** - Field names and types explain themselves
4. **Easier refactoring** - Rename a field, compiler finds all usages
5. **Consistent flow** - Input/output pairs are enforced by type system
