# Agent/Session Refactor Design

## Problem

The current agent and session construction is messy and inflexible:
- Agent is created per-session inside `ChatLoop.run()`
- AgentSession mixes runtime state with persistence logic
- AgentSession is an async context manager but all operations are sync
- Agent creates ToolRegistry internally, hard to customize
- ChatLoop has too much wiring responsibility (6+ classes)

Future features (skills, multi-agent) will require more flexibility.

## Proposed Architecture

```
SharedContext (config, history_store)
       |
       └── Agent (agent_config, llm, tools)
              |
              └── Session (session_id, messages)
```

### Key Principle: Agent is one level above Session

- **Agent** = Reusable "persona" with specific LLM, tools, and configuration
- **Session** = Single conversation with message history

## Components

### SharedContext

Global shared state for the application.

```python
@dataclass
class SharedContext:
    """Global shared state for the application."""
    config: Config
    history_store: HistoryStore
```

### Agent

A configured agent that can handle multiple conversations.

```python
@dataclass
class Agent:
    """A configured agent that can handle multiple conversations."""

    agent_config: AgentConfig          # name, system_prompt, behavior
    llm: LLMProvider                   # Model to use
    tools: ToolRegistry                # Available tools
    context: SharedContext             # Access to history, config

    _sessions: dict[str, Session] = field(default_factory=dict)

    def new_session(self) -> Session:
        """Create a new conversation session."""
        session_id = str(uuid4())
        self.context.history_store.create_session(
            agent_id=self.agent_config.name,
            session_id=session_id
        )
        session = Session(
            session_id=session_id,
            agent_id=self.agent_config.name,
            history_store=self.context.history_store
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        """Get an existing session (from memory or load from history)."""
        ...

    async def chat(self, session: Session, message: str, frontend: Frontend) -> str:
        """Send a message in a session and get response."""
        ...

    def _build_messages(self, session: Session) -> list[Message]:
        """Build messages for LLM API call."""
        return [
            {"role": "system", "content": self.agent_config.system_prompt},
            *session.get_history(50)
        ]
```

### Session

Runtime state for a single conversation. Lightweight, no async context manager.

```python
@dataclass
class Session:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    history_store: HistoryStore

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """Add a message to history (in-memory + persist)."""
        self.messages.append(message)
        self._persist_message(message)

    def get_history(self, max_messages: int = 50) -> list[Message]:
        """Get recent messages for LLM context."""
        return self.messages[-max_messages:]

    def _persist_message(self, message: Message) -> None:
        """Save to HistoryStore."""
        ...
```

### Frontend

Frontend is passed to `chat()` per-call, not held by Agent. This enables:
- Multiple frontends for different channels (CLI, web, message bus)
- Flexibility to plumb frontends in and out

```python
# CLI
response = await agent.chat(session, message, console_frontend)

# Web
response = await agent.chat(session, message, web_frontend)

# Message bus
response = await agent.chat(session, message, bus_frontend)
```

## Construction Flow

### Before (Current)

```python
class ChatLoop:
    def __init__(self, config: Config):
        self.config = config
        self.frontend = ConsoleFrontend(config.agent)
        self.history_store = HistoryStore.from_config(config)

    async def run(self):
        async with AgentSession(...) as session:
            self.agent = Agent(config, session, frontend, llm)
            # ... chat loop
```

### After (Proposed)

```python
class ChatLoop:
    def __init__(self, config: Config):
        self.config = config
        self.frontend = ConsoleFrontend(config.agent)

        # Shared layer
        self.context = SharedContext(
            config=config,
            history_store=HistoryStore.from_config(config)
        )

        # Agent (reusable, created once)
        self.agent = Agent(
            agent_config=config.agent,
            llm=LLMProvider.from_config(config.llm),
            tools=ToolRegistry.with_builtins(),
            context=self.context
        )

    async def run(self):
        session = self.agent.new_session()
        self.frontend.show_welcome()

        while True:
            user_input = self.frontend.get_user_input()
            if user_input in ["quit", "exit", "q"]:
                break
            response = await self.agent.chat(session, user_input, self.frontend)
            self.frontend.show_agent_response(response)
```

## Changes Required

1. **New: `SharedContext`** - Dataclass in `core/context.py` or `core/shared.py`
2. **Refactor: `Agent`** - Update constructor, add `new_session()`, change `chat()` signature
3. **Refactor: `Session`** - Rename from `AgentSession`, simplify, remove async context manager
4. **Refactor: `ChatLoop`** - Update construction flow
5. **Optional: `ToolRegistry.with_builtins()`** - Factory method for cleaner construction

## Future Extensibility

This design supports:
- **Skills system**: Add `SkillRegistry` to Agent, similar to `ToolRegistry`
- **Multi-agent**: Add agent registry to `SharedContext` when needed
- **Multiple frontends**: Frontend is passed per-call, easy to swap
- **Session resumption**: `Agent.get_session(session_id)` can load from history
