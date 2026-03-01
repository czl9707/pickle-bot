# Session Source Persistence Design

## Problem

The current session system uses a `SessionMode` enum (CHAT/JOB) to control behavior, but this is disconnected from the actual source of the session. The `source` field on events tells us where work comes from (platforms, cron, subagents), but sessions don't persist this information.

Additionally, `SessionMode` creates an unnecessary abstraction - what we really care about is "where did this session come from" and "what settings apply to that source."

## Solution

Remove `SessionMode` entirely. Sessions will persist their `source` and `context` (MessageContext) at creation time. Behavior (max_history, tool availability) is derived from the source string.

## Design

### Source → Settings Mapping

A simple helper function determines settings based on source:

```python
def get_source_settings(source: str) -> tuple[int, bool]:
    """Returns (max_history, post_message) for a given source."""
    if source.startswith("cron:"):
        return (50, True)
    return (100, False)
```

| Source Pattern | max_history | post_message |
|----------------|-------------|--------------|
| `cron:*` | 50 | True |
| Everything else | 100 | False |

### Data Model Changes

**HistorySession** (persisted to `index.jsonl`):
```python
class HistorySession(BaseModel):
    id: str
    agent_id: str
    source: str                              # NEW: e.g., "telegram:user_123"
    context: dict[str, Any] | None = None   # NEW: serialized MessageContext
    chunk_count: int = 1
    title: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str
```

**AgentSession** (runtime):
```python
@dataclass
class AgentSession:
    session_id: str
    agent_id: str
    source: str                              # NEW
    context: MessageContext | None           # NEW: typed object
    context: "SharedContext"
    agent: Agent
    tools: ToolRegistry
    max_history: int                         # Derived from source
    # REMOVED: mode: SessionMode

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
```

### API Changes

**Agent.new_session**:
```python
def new_session(
    self,
    source: str,
    context: MessageContext | None = None,
    session_id: str | None = None,
) -> AgentSession:
```

**Agent.resume_session**:
```python
def resume_session(self, session_id: str) -> AgentSession:
    # Loads stored source + context from HistorySession
    # Derives max_history from source via get_source_settings()
    # Builds tools based on source settings
```

**HistoryStore.create_session**:
```python
def create_session(
    self,
    agent_id: str,
    session_id: str,
    source: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

### Worker Changes

**AgentWorker.SessionExecutor**:
```python
source = event.source
context = event.context if isinstance(event, InboundEvent) else None

if session_id:
    session = agent.resume_session(session_id)
else:
    session = agent.new_session(source, context)
```

**MessageBusWorker**:
```python
session = agent.new_session(
    source=Source.platform(platform, user_id),
    context=context,
)
```

**CronWorker**:
```python
session = agent.new_session(
    source=Source.cron(cron_id),
    context=None,
)
```

### Migration

Existing sessions without `source` field will default to `source="unknown"` and `context=None` when resumed, resulting in CHAT behavior.

```python
source = session_info.source or "unknown"
context = _deserialize_context(session_info.context)
```

## Files Changed

| File | Change |
|------|--------|
| `core/agent.py` | Remove `SessionMode`, update `new_session`/`resume_session`, add `get_source_settings` |
| `core/history.py` | Add `source`, `context` to `HistorySession`, update `create_session` |
| `server/agent_worker.py` | Pass source/context from event to session |
| `server/messagebus_worker.py` | Pass source/context to `new_session` |
| `server/cron_worker.py` | Pass source to `new_session` |
| `tools/subagent_tool.py` | Update imports, remove SessionMode usage |

## Benefits

- Sessions know their origin - useful for debugging, analytics, reply routing
- Simpler mental model - no separate "mode" concept
- Extensible - add more source-based logic in one place
- Platform context persists - can reply to old sessions correctly
