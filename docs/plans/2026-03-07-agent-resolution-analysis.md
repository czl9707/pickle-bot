# Agent-ID Resolution Analysis

Date: 2026-03-07
Status: Research Complete

## Current Flow

### 1. Message Arrival (ChannelWorker)
```python
# server/channel_worker.py:60-63
agent_id = self.context.routing_table.resolve(str(source))
session_id = self.context.routing_table.get_or_create_session_id(source, agent_id)

event = InboundEvent(
    session_id=session_id,
    agent_id=agent_id,  # From routing resolution
    source=source,
    content=message,
    timestamp=time.time(),
)
```

### 2. Session ID Resolution (RoutingTable)
```python
# core/routing.py:79-106
def get_or_create_session_id(self, source: EventSource, agent_id: str) -> str:
    source_str = str(source)

    # Check cache first - NOTE: Returns cached session regardless of agent_id!
    source_info = self._context.config.sources.get(source_str)
    if source_info:
        return source_info["session_id"]  # Agent_id parameter is ignored!

    # Create new session only if not cached
    agent_def = self._context.agent_loader.load(agent_id)
    agent = Agent(agent_def, self._context)
    session = agent.new_session(source)

    # Cache the session
    self._context.config.set_runtime(
        f"sources.{source_str}", {"session_id": session.session_id}
    )

    return session.session_id
```

### 3. Session Persistence (HistoryStore)
```python
# core/history.py:22-44
class HistorySession(BaseModel):
    id: str
    agent_id: str  # Persisted with session
    source: str    # Serialized EventSource
    title: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str
```

### 4. Event Processing (AgentWorker)
```python
# server/agent_worker.py:54-72
async def dispatch_event(self, event: ProcessableEvent) -> None:
    agent_id = event.agent_id  # From event (set by ChannelWorker)

    try:
        agent_def = self.context.agent_loader.load(agent_id)
        # ...
        asyncio.create_task(self.exec_session(event, agent_def))

async def exec_session(self, event: ProcessableEvent, agent_def: "AgentDef") -> None:
    # ...
    agent = Agent(agent_def, self.context)
    if session_id:
        session = agent.resume_session(session_id)  # Loads old session
```

### 5. Session Resume (Agent)
```python
# core/agent.py:135-188
def resume_session(self, session_id: str) -> "AgentSession":
    session_info = self.context.history_store.list_sessions()
    # ... find session ...

    # NOTE: Uses self.agent_def (from AgentWorker)
    # Does NOT verify session_info.agent_id == self.agent_def.id

    return AgentSession(
        agent=self,  # This Agent has the NEW agent_def from routing
        state=state,  # But this state was created with OLD agent
        # ...
    )
```

## The Problem: Routing Changes Cause Agent Mismatch

### Scenario 1: Source is Cached
1. **Initial State**: User sends message from `platform-telegram:user:123`
2. **Routing**: `platform-telegram:.*` → `pickle`
3. **Result**:
   - Session created: `{id: "abc", agent_id: "pickle", source: "platform-telegram:user:123"}`
   - Source cached: `sources["platform-telegram:user:123"] = {session_id: "abc"}`

4. **User Changes Routing**: Updates to `platform-telegram:.*` → `cookie`
5. **Next Message**:
   - `resolve()` returns `cookie` (new routing)
   - `get_or_create_session_id()` finds cached session_id `"abc"` (ignores `agent_id` parameter!)
   - Event: `{agent_id: "cookie", session_id: "abc"}`
   - AgentWorker loads `cookie` agent definition
   - AgentWorker calls `cookie_agent.resume_session("abc")`
   - **Session "abc" was created with agent_id "pickle"!**

### Scenario 2: Session Exists in History (No Cache)
Same mismatch occurs if:
- Server restarts (runtime cache cleared)
- Session cache manually cleared
- But session still exists in history

The agent loaded is from current routing, but session is from old routing.

## Current Behavior Analysis

### What Actually Happens?
When there's a mismatch:
- Agent definition loaded: `cookie` (from current routing)
- Session history loaded: Created with `pickle`
- AgentSession created with:
  - `agent`: Cookie agent definition
  - `state.source`: From history (correct)
  - `state.messages`: From history (correct)
  - Tools: Cookie's tools (from `agent_def.allow_skills`, etc.)
  - System prompt: Cookie's prompt (not Pickle's!)

### Is This a Problem?
**Yes, potentially:**

1. **Tool Mismatch**:
   - Session was with Pickle (has skills enabled)
   - Now running with Cookie (might not have skills)
   - Old tool calls in history might not make sense

2. **Prompt Mismatch**:
   - Conversation started with Pickle's personality
   - Suddenly switches to Cookie's personality
   - Context becomes confusing for LLM and user

3. **Agent-Specific State**:
   - If agents have different configurations (temperature, max_tokens)
   - Could affect conversation quality

## Current Mitigations

### None Found
- No validation that `session.agent_id == loaded_agent.id`
- No warning or error when mismatch occurs
- No mechanism to detect routing changes

## Questions for Design Discussion

1. **Expected Behavior**: What SHOULD happen when routing changes for an active source?
   - Continue existing session with old agent? (ignore routing change)
   - Start new session with new agent? (lose conversation history)
   - Hybrid: Keep history but switch agent? (current behavior)

2. **Session Affinity**: Should sessions be "bound" to their original agent?
   - If yes: Routing changes only affect NEW sessions
   - If no: Routing changes affect existing sessions (current behavior)

3. **User Experience**: What's least surprising?
   - User changes routing, expects immediate effect?
   - Or expects conversations to continue with same agent?

4. **Implementation**: Where should this logic live?
   - ChannelWorker? (before session resolution)
   - RoutingTable? (during session resolution)
   - AgentWorker? (before session resume)
   - Agent.resume_session? (during session load)

## Code Locations Summary

| Component | File | Lines | Responsibility |
|-----------|------|-------|----------------|
| Routing Resolution | `core/routing.py` | 72-77 | Match source to agent_id |
| Session Cache | `core/routing.py` | 79-106 | Get/create session_id |
| Event Creation | `server/channel_worker.py` | 60-73 | Set agent_id + session_id |
| Event Dispatch | `server/agent_worker.py` | 54-72 | Load agent by agent_id |
| Session Resume | `core/agent.py` | 135-188 | Load session from history |
| Session Persistence | `core/history.py` | 22-44 | Store agent_id with session |
