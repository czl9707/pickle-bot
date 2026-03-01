# Event System Refactor Design

## Problem

The current event system in `core/events.py` has significant duplication:
- Four event classes with near-identical structure and boilerplate
- Each has identical `to_dict()`, `from_dict()`, `type` property code
- The old `Event` class is unused but still imported
- `deserialize_event()` uses an if-elif chain
- Event construction requires `timestamp=time.time()` everywhere

## Solution

Refactor to use inheritance with a base `Event` class that handles common functionality.

## Design

### Base Event Class

```python
@dataclass
class Event:
    session_id: str
    agent_id: str
    source: str
    content: str
    timestamp: float = field(default_factory=time.time)

    @property
    def type(self) -> EventType:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Self":
        data = data.copy()
        data.pop("type", None)
        return cls(**data)
```

### Typed Events

Each event type inherits from `Event` and defines only its specific fields plus the `type` property:

- **InboundEvent**: `context`, `retry_count`
- **OutboundEvent**: `error`
- **DispatchEvent**: `parent_session_id`, `retry_count`
- **DispatchResultEvent**: `error`

### Deserialization Registry

Replace if-elif chain with a registry:

```python
_EVENT_CLASSES: dict[EventType, type[Event]] = {
    EventType.INBOUND: InboundEvent,
    EventType.OUTBOUND: OutboundEvent,
    EventType.DISPATCH: DispatchEvent,
    EventType.DISPATCH_RESULT: DispatchResultEvent,
}

def deserialize_event(data: dict[str, Any]) -> Event:
    event_type = EventType(data["type"])
    cls = _EVENT_CLASSES[event_type]
    return cls.from_dict(data)
```

### Cleanup

- Remove `TypedEvent` type alias (use `Event` directly)
- Update all imports across the codebase
- Update `AnyEvent` union in `eventbus.py` to just be `Event`

## Files Changed

| File | Change |
|------|--------|
| `core/events.py` | Major refactor - inheritance-based events |
| `core/eventbus.py` | Update imports and type annotations |
| `server/agent_worker.py` | Update imports |
| `server/messagebus_worker.py` | Update imports |
| `server/cron_worker.py` | Update imports |
| `server/delivery_worker.py` | Update imports |
| `tools/subagent_tool.py` | Update imports |
| `tools/post_message_tool.py` | Update imports |

## Benefits

- Eliminates ~100 lines of duplicated code
- Auto-timestamp removes repetitive `time.time()` calls
- Registry pattern is extensible for new event types
- Single `Event` base type simplifies type annotations
