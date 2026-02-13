# Session Chat Refactor Design

## Problem

Current `agent.chat(session, message, frontend)` is verbose - session is passed to agent, then agent does the work. Conceptually, the session should own the chat interaction.

## Solution

Move `chat()` from Agent to Session. Agent becomes a factory for sessions.

```python
# Before
session = agent.new_session()
response = await agent.chat(session, message, frontend)

# After
session = agent.new_session()
response = await session.chat(message, frontend)
```

## Design

### Session holds Agent reference

Session gets access to LLM, tools, and config via `self.agent`.

```python
@dataclass
class Session:
    session_id: str
    agent_id: str
    history_store: HistoryStore
    agent: Agent  # NEW

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    async def chat(self, message: str, frontend: "Frontend") -> str:
        """Send message and get response using self.agent's LLM/tools."""
        ...
```

### Agent becomes factory + holder

Agent no longer has `chat()`. It's a data holder and session factory.

```python
@dataclass
class Agent:
    agent_config: AgentConfig
    llm: LLMProvider
    tools: ToolRegistry
    context: SharedContext

    def new_session(self) -> Session:
        """Create a new session with self as agent reference."""
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            agent_id=self.agent_config.name,
            history_store=self.context.history_store,
            agent=self,  # NEW: pass self reference
        )
        self.context.history_store.create_session(self.agent_config.name, session_id)
        return session
```

### Frontend passed per-call

Frontend stays as a per-call parameter for flexibility (same session can use different frontends).

## Implementation

| File | Change |
|------|--------|
| `core/session.py` | Add `agent` field, move chat methods from Agent |
| `core/agent.py` | Remove `chat()` and helpers, update `new_session()` |
| `cli/chat.py` | Change `agent.chat(...)` to `session.chat(...)` |

## Result

- Cleaner API: `session.chat(message, frontend)`
- Agent is ~30 lines (factory + config holder)
- Session owns the conversation lifecycle
