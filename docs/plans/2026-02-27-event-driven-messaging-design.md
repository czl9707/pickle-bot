# Event-Driven Messaging Architecture Design

Date: 2026-02-27

## Overview

Replace the current messy frontend/reply/post mechanism with a unified event-driven architecture. All outbound messaging flows through a central EventBus with filesystem persistence for reliability.

## Goals

- Single unified path for all outbound messages
- Crash-safe message delivery with write-ahead persistence
- Decouple event creation from delivery method
- Enable WebSocket integration for monitoring/external integrations
- Simplify the codebase by removing Frontend abstraction

## Event Types

| Type | Persisted | Delivered to Platform | Broadcast to WebSocket |
|------|-----------|----------------------|------------------------|
| `InboundMessage` | No | No | Yes |
| `OutboundMessage` | Yes | Yes | Yes |
| `StatusUpdate` | No | No | Yes |

## Event Structure

Platform-agnostic - no delivery details, just session context:

```python
@dataclass
class Event:
    type: EventType      # INBOUND / OUTBOUND / STATUS
    session_id: str      # which conversation
    content: str         # the actual message/status
    source: str          # who created this (e.g., "telegram:user_123", "agent:pickle")
    timestamp: float     # when created
    metadata: dict       # optional extras (agent_id, tool_name, etc.)
```

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │             EventBus                │
                         │                                     │
 INBOUND                 │  publish(event):                    │
─────────────────────►   │    1. if OUTBOUND: persist to disk  │
                         │    2. notify subscribers            │
                         │                                     │
                         │  subscribe(type, handler)           │
                         └──────────────┬──────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │DeliveryWorker│   │WebSocketStub │   │    Agent     │
            │              │   │              │   │ (subscribes  │
            │ OUTBOUND only│   │ ALL events   │   │  INBOUND)    │
            └──────┬───────┘   └──────────────┘   └──────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
Telegram       Discord          CLI
```

## EventBus

**Responsibilities:**
1. Persist OutboundMessage events (write-ahead, before notifying subscribers)
2. Notify subscribers (in-memory, async)
3. Recover on startup (scan persisted but undelivered events)

**Persistence:**
- Directory: `~/.events/pending/`
- Write: `tmp + fsync + os.replace` (atomic)
- File format: `{timestamp}_{session_id}.json`
- Ack: Delete file after successful delivery (called by DeliveryWorker)

**Recovery:**
- On startup, scan `pending/` directory
- Re-publish any files still there (crash before delivery)

## DeliveryWorker

**Responsibilities:**
1. Subscribe to `OutboundMessage` events
2. Look up session -> platform + delivery context
3. Chunk message if exceeds platform limit
4. Deliver via appropriate method
5. On success: `eventbus.ack(event)` (deletes persisted file)
6. On failure: Retry with backoff

**Chunking:**

```python
LIMITS = {
    "telegram": 4096,
    "discord": 2000,
    "cli": float("inf"),  # no limit
}

def chunk_message(content: str, limit: int) -> list[str]:
    """Split message at paragraph boundaries, respecting limit."""
    # Splits at paragraph boundaries first
    # Falls back to hard split if single paragraph exceeds limit
```

- Each chunk delivered as separate message
- All chunks must succeed before `ack()`
- If any chunk fails, retry entire event

**Retry logic:**
- Backoff schedule: `[5s, 25s, 2min, 10min]` with +/-20% jitter
- Max retries: 5
- After max retries: Move to `~/.events/failed/`

**Session -> Platform lookup:**
- DeliveryWorker does the lookup work (no config changes for now)
- Session management revamp comes later
- CLI is just another platform - no special handling

## WebSocketWorker (Stub)

Placeholder for future implementation:
- Subscribe to all events (InboundMessage, OutboundMessage, StatusUpdate)
- Broadcast events to connected WebSocket clients
- No persistence needed

## Integration Points

### Incoming Messages (MessageBusWorker)

```python
event = Event(
    type=EventType.INBOUND,
    session_id=session_id,
    content=message,
    source=f"telegram:{context.user_id}",
    timestamp=time.time(),
    metadata={"chat_id": context.chat_id},
)
await eventbus.publish(event)
```

### Outgoing Messages (Agent/Session)

```python
event = Event(
    type=EventType.OUTBOUND,
    session_id=self.session_id,
    content=content,
    source=f"agent:{agent_id}",
    timestamp=time.time(),
    metadata={"agent_id": agent_id},
)
await eventbus.publish(event)
```

### Proactive Messages (post_message_tool)

```python
event = Event(
    type=EventType.OUTBOUND,
    session_id=session_id,
    content=content,
    source="tool:post_message",
    timestamp=time.time(),
    metadata={},
)
await eventbus.publish(event)
```

## File Structure

**New files:**

```
src/picklebot/
├── events/
│   ├── __init__.py
│   ├── types.py          # Event, EventType dataclass
│   ├── bus.py            # EventBus class
│   ├── delivery.py       # DeliveryWorker + chunking logic
│   └── websocket.py      # WebSocketWorker stub
```

**Modified files:**

```
src/picklebot/
├── core/
│   ├── agent.py          # Publish OutboundMessage events
│   ├── session.py        # Same
│   └── context.py        # Add eventbus to SharedContext
├── server/
│   ├── messagebus_worker.py  # Publish InboundMessage events
│   └── server.py            # Start DeliveryWorker
├── tools/
│   └── post_message_tool.py # Publish event instead of bus.post()
└── cli/
    └── chat.py              # Subscribe to events, no blocking
```

**Deleted:**

```
src/picklebot/
└── frontend/                # DELETE entire folder
    ├── base.py
    ├── console.py
    └── messagebus.py
```

## Migration Path

**Phase 1: Core Infrastructure**
1. Create `events/` module with `Event`, `EventType`, `EventBus`
2. Implement persistence (write-ahead, ack, recovery)
3. Add eventbus to `SharedContext`

**Phase 2: DeliveryWorker**
1. Implement DeliveryWorker with chunking
2. Implement session -> platform lookup
3. Wire up Telegram, Discord, CLI delivery methods
4. Start DeliveryWorker in server.py

**Phase 3: Replace Output Paths**
1. Agent/Session -> publish OutboundMessage instead of frontend.show_message()
2. post_message_tool -> publish event
3. Remove Frontend folder

**Phase 4: Replace Input Paths**
1. MessageBusWorker -> publish InboundMessage event
2. CLI -> async, subscribe to events, no blocking
3. Wire up agent to consume InboundMessage events

**Phase 5: WebSocketWorker Stub**
1. Create stub with comments describing future implementation

## Key Decisions

- EventBus handles persistence internally (write-ahead for OUTBOUND)
- DeliveryWorker does session -> platform lookup (no config changes)
- CLI is just another platform in DeliveryWorker, no blocking
- Frontend abstraction removed entirely
- WebSocketWorker stub for future implementation
- Chunking implemented now for platform limits
