# Agent-ID Resolution Design

Date: 2026-03-07
Status: Approved
Related: [Agent-ID Resolution Analysis](2026-03-07-agent-resolution-analysis.md)

## Problem Statement

Current architecture allows agent-id in events to diverge from agent-id persisted in sessions, causing agent mismatch when routing changes mid-conversation.

### Current Behavior

When a user changes routing for a source with an active session:

1. **Agent switches**: New agent-id from routing resolution
2. **Session persists**: Old session-id from cache
3. **Result**: New agent processes old agent's conversation history

**Example:**
```
Initial: telegram:user:123 → pickle (session "abc", agent_id="pickle")
Change: telegram:user:123 → cookie
Next message:
  - routing_table.resolve() → "cookie"
  - routing_table.get_or_create_session_id() → "abc" (cached)
  - Event: {agent_id="cookie", session_id="abc"}
  - AgentWorker loads cookie agent, resumes pickle session
  - MISMATCH: Cookie running Pickle's conversation
```

### Root Cause

The `agent_id` field in Event class creates a second source of truth that can diverge from the session's agent_id:

```python
# core/routing.py:92-94
source_info = self._context.config.sources.get(source_str)
if source_info:
    return source_info["session_id"]  # Returns session, ignores agent_id param!
```

## Design Solution

Remove `agent_id` from the Event base class. All agent resolution happens through session lookup, guaranteeing session affinity.

## Architecture Changes

### 1. Event Class Structure

**Current:**
```python
@dataclass
class Event:
    session_id: str
    agent_id: str  # REMOVING THIS
    source: EventSource
    content: str
    timestamp: float
```

**New:**
```python
@dataclass
class Event:
    session_id: str
    source: EventSource
    content: str
    timestamp: float = field(default_factory=time.time)
```

**Rationale:** agent_id is redundant because:
- InboundEvent: agent_id available from session
- DispatchEvent: session already created with correct agent
- OutboundEvent/DispatchResultEvent: agent info in AgentEventSource

### 2. Agent Resolution Logic

**Current (agent_worker.py):**
```python
async def dispatch_event(self, event: ProcessableEvent) -> None:
    agent_id = event.agent_id  # From event - can mismatch!
    agent_def = self.context.agent_loader.load(agent_id)
```

**New:**
```python
async def dispatch_event(self, event: ProcessableEvent) -> None:
    # Get agent_id from session (single source of truth)
    session_info = self.context.history_store.get_session_info(event.session_id)
    agent_id = session_info.agent_id

    try:
        agent_def = self.context.agent_loader.load(agent_id)
        # ... rest of logic unchanged
```

**Impact:** All event types now use session as single source of truth for agent identity.

### 3. Event Creation Sites

#### 3.1 ChannelWorker (InboundEvent)

**Current:**
```python
# server/channel_worker.py:60-68
agent_id = self.context.routing_table.resolve(str(source))
session_id = self.context.routing_table.get_or_create_session_id(
    source, agent_id
)

event = InboundEvent(
    session_id=session_id,
    agent_id=agent_id,  # From routing
    source=source,
    content=message,
    timestamp=time.time(),
)
```

**New:**
```python
# server/channel_worker.py
session_id = self.context.routing_table.get_or_create_session_id(source)

event = InboundEvent(
    session_id=session_id,
    source=source,
    content=message,
    timestamp=time.time(),
)
```

**Note:** Routing still determines agent for NEW sessions, but not for existing sessions.

#### 3.2 CronWorker (DispatchEvent)

**Current:**
```python
# server/cron_worker.py:84-89
event = DispatchEvent(
    session_id=session.session_id,
    agent_id=cron_def.agent,  # Redundant - already in session
    source=CronEventSource(cron_id=cron_def.id),
    content=cron_def.prompt,
)
```

**New:**
```python
event = DispatchEvent(
    session_id=session.session_id,
    source=CronEventSource(cron_id=cron_def.id),
    content=cron_def.prompt,
)
```

**Note:** Session already created with correct agent on line 82.

#### 3.3 Subagent Tool (DispatchEvent)

**Current:**
```python
# tools/subagent_tool.py:122-129
event = DispatchEvent(
    session_id=session_id,
    agent_id=agent_id,  # Redundant - already in session
    source=AgentEventSource(agent_id=current_agent_id),
    content=user_message,
    timestamp=time.time(),
    parent_session_id=session.session_id,
)
```

**New:**
```python
event = DispatchEvent(
    session_id=session_id,
    source=AgentEventSource(agent_id=current_agent_id),
    content=user_message,
    timestamp=time.time(),
    parent_session_id=session.session_id,
)
```

**Note:** Session created with correct agent on line 98.

#### 3.4 AgentWorker Response Events

**Current:**
```python
# server/agent_worker.py:144-158
if isinstance(event, DispatchEvent):
    return DispatchResultEvent(
        session_id=event.session_id,
        agent_id=agent_id,  # Redundant - in source
        source=AgentEventSource(agent_id),
        content=content,
        error=str(error) if error else None,
    )
else:
    return OutboundEvent(
        session_id=event.session_id,
        agent_id=agent_id,  # Redundant - in source
        source=AgentEventSource(agent_id),
        content=content,
        error=str(error) if error else None,
    )
```

**New:**
```python
if isinstance(event, DispatchEvent):
    return DispatchResultEvent(
        session_id=event.session_id,
        source=AgentEventSource(agent_id),  # Agent info here
        content=content,
        error=str(error) if error else None,
    )
else:
    return OutboundEvent(
        session_id=event.session_id,
        source=AgentEventSource(agent_id),  # Agent info here
        content=content,
        error=str(error) if error else None,
    )
```

**Note:** Agent info preserved in AgentEventSource for consumers that need it.

#### 3.5 Post Message Tool (OutboundEvent)

**Current:**
```python
# tools/post_message_tool.py:61-67
event = OutboundEvent(
    session_id=session.session_id,
    agent_id=session.agent.agent_def.id,  # Redundant - in source
    source=AgentEventSource(agent_id=session.agent.agent_def.id),
    content=content,
    timestamp=time.time(),
)
```

**New:**
```python
event = OutboundEvent(
    session_id=session.session_id,
    source=AgentEventSource(agent_id=session.agent.agent_def.id),
    content=content,
    timestamp=time.time(),
)
```

### 4. RoutingTable Changes

**Current:**
```python
# core/routing.py:79-106
def get_or_create_session_id(self, source: EventSource, agent_id: str) -> str:
    source_str = str(source)

    # Check cache first
    source_info = self._context.config.sources.get(source_str)
    if source_info:
        return source_info["session_id"]  # Ignores agent_id param!

    # Create new session
    agent_def = self._context.agent_loader.load(agent_id)  # Uses param
    agent = Agent(agent_def, self._context)
    session = agent.new_session(source)

    # Cache the session
    self._context.config.set_runtime(
        f"sources.{source_str}", {"session_id": session.session_id}
    )

    return session.session_id
```

**New:**
```python
def get_or_create_session_id(self, source: EventSource) -> str:
    """Get existing or create new session_id for source.

    For existing sessions, returns cached session_id (session affinity).
    For new sessions, resolves agent from routing table.
    """
    source_str = str(source)

    # Check cache first (existing session)
    source_info = self._context.config.sources.get(source_str)
    if source_info:
        return source_info["session_id"]

    # New session: resolve agent from routing
    agent_id = self.resolve(source_str)

    # Create new session
    agent_def = self._context.agent_loader.load(agent_id)
    agent = Agent(agent_def, self._context)
    session = agent.new_session(source)

    # Cache the session
    self._context.config.set_runtime(
        f"sources.{source_str}", {"session_id": session.session_id}
    )

    return session.session_id
```

**Key change:** agent_id no longer a parameter. Routing only consulted for NEW sessions.

## Behavior Changes

### Before (Current)
- Routing changes immediately affect existing sessions
- Agent mismatch when routing changes mid-conversation
- agent_id can diverge between event and session

### After (New Design)
- **Session affinity**: Existing sessions continue with their original agent
- Routing changes only affect NEW conversations
- agent_id single source of truth in session
- Users must use `/clear` to switch agents mid-conversation

**Example with new design:**
```
Initial: telegram:user:123 → pickle (session "abc", agent_id="pickle")
Change: telegram:user:123 → cookie
Next message:
  - get_or_create_session_id() → "abc" (cached)
  - AgentWorker gets agent_id from session "abc" → "pickle"
  - Continues with pickle (session affinity)
  - User explicitly /clear to start new session with cookie
```

## Migration Impact

### Code Changes Required

1. **core/events.py** - Remove agent_id from Event base class
2. **server/agent_worker.py** - Get agent from session, remove from event creation
3. **server/channel_worker.py** - Remove agent_id from InboundEvent creation
4. **server/cron_worker.py** - Remove agent_id from DispatchEvent creation
5. **tools/subagent_tool.py** - Remove agent_id from DispatchEvent creation
6. **tools/post_message_tool.py** - Remove agent_id from OutboundEvent creation
7. **core/routing.py** - Remove agent_id parameter from get_or_create_session_id()

### Test Updates Required

All tests that create events will need updates:
- Remove agent_id from event construction
- Update mock expectations

### Database Migration

**None required** - sessions already persist agent_id in HistorySession.

### Backward Compatibility

**Breaking change for event serialization:**
- Old events (with agent_id) will fail deserialization
- Recommend clearing event queue before deployment
- Or implement backward-compatible deserialization (ignore unknown field)

## Benefits

✅ **Session affinity guaranteed** - Agent bound to session lifecycle
✅ **Single source of truth** - agent_id only in session
✅ **No redundant fields** - Cleaner architecture
✅ **Routing changes safe** - Only affect new sessions
✅ **Predictable behavior** - Users understand session = agent
✅ **Simpler debugging** - One place to check agent identity

## Edge Cases

### Q: What if user wants to switch agents mid-conversation?
**A:** Use `/clear` command to start fresh session. Routing will then apply to new session.

### Q: What if session's agent is deleted?
**A:** AgentWorker will fail to load agent_def, same as current behavior. Error propagates to user.

### Q: What about OutboundEvent consumers that need agent_id?
**A:** Use `source.agent_id` from AgentEventSource. No information lost.

### Q: What if routing table is empty?
**A:** Same as current - falls back to default_agent for new sessions.

## Testing Strategy

1. **Unit tests:**
   - Event creation without agent_id
   - AgentWorker agent resolution from session
   - RoutingTable session affinity

2. **Integration tests:**
   - Routing change mid-conversation stays with original agent
   - New conversation after routing change uses new agent
   - `/clear` creates new session with current routing

3. **Migration tests:**
   - Existing sessions continue to work
   - Event deserialization handles missing agent_id

## Implementation Order

1. Update Event class (core/events.py)
2. Update AgentWorker (server/agent_worker.py)
3. Update event creators (5 locations)
4. Update RoutingTable (core/routing.py)
5. Update tests
6. Manual testing with routing changes

## Success Criteria

- [ ] All event types created without agent_id
- [ ] AgentWorker resolves agent from session
- [ ] Routing changes don't affect existing sessions
- [ ] `/clear` creates new session with current routing
- [ ] All tests pass
- [ ] No event deserialization errors
