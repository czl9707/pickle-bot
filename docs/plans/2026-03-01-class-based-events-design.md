# Class-Based Events Design

## Problem

The current event system uses both an `EventType` enum and event classes, creating redundancy. The `event.type` property duplicates class information. Additionally, `subscribe()` uses `EventType` instead of class types, forcing handlers to accept generic `Event` and making mypy unable to verify handler signatures.

## Solution

Remove `EventType` enum entirely. Use event classes directly for:
- Subscription routing (key by class type)
- Serialization (use class name)
- Type checking (use `isinstance`)

## Design

### Remove

- `EventType` enum
- `event.type` property from `Event` and all subclasses

### Event Class Changes

**`Event` base class:**
```python
@dataclass
class Event:
    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float = field(default_factory=time.time)

    # Remove: type property

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.__class__.__name__}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name == "context":
                result[field_name] = _serialize_context(value)
            else:
                result[field_name] = value
        return result
```

**Subclasses - remove `type` property:**
```python
@dataclass
class InboundEvent(Event):
    retry_count: int = 0
    context: MessageContext | None = None
    # Remove: type property
```

### EventBus Changes

**Subscribers storage keyed by class:**
```python
_subscribers: dict[type[Event], list[Handler]]
```

**Generic subscribe method:**
```python
from typing import TypeVar

E = TypeVar("E", bound=Event)

def subscribe(
    self,
    event_class: type[E],
    handler: Callable[[E], Awaitable[None]]
) -> None:
    self._subscribers[event_class].append(handler)
```

**Dispatch by class type:**
```python
def _notify_subscribers(self, event: Event) -> None:
    handlers = self._subscribers.get(type(event), [])
    ...
```

**Persistence check uses isinstance:**
```python
def _persist_outbound(self, event: Event) -> None:
    if not isinstance(event, OutboundEvent):
        return
    ...
```

### Serialization Changes

**Registry keyed by class name:**
```python
_EVENT_CLASSES: dict[str, type[Event]] = {
    "InboundEvent": InboundEvent,
    "OutboundEvent": OutboundEvent,
    "DispatchEvent": DispatchEvent,
    "DispatchResultEvent": DispatchResultEvent,
}
```

**Deserialize by class name:**
```python
def deserialize_event(data: dict[str, Any]) -> Event:
    event_type: str = data.get("type")  # "InboundEvent", etc.
    event_class = _EVENT_CLASSES.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")
    return event_class.from_dict(data)
```

## Files Changed

| File | Change |
|------|--------|
| `core/events.py` | Remove EventType, remove type property, update registry |
| `core/eventbus.py` | Generic subscribe, dispatch by type(event), isinstance check |

## Benefits

- **No redundancy** - Class is the single source of truth for event type
- **Type-safe subscriptions** - mypy verifies handler matches event class
- **Cleaner code** - Less boilerplate (no type property on each class)
- **Simpler mental model** - Just classes, no parallel enum hierarchy
