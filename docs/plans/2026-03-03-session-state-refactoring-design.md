# Session State Refactoring - Design

> Fix session rolling by introducing SessionState as a swappable data container.

## Problem

Current session rolling has a bug: when `ContextGuard` rolls to a new session, it creates a new `AgentSession` and updates the config mapping, but the in-memory `AgentSession` object continues to be used. This causes:

1. In-flight messages (during the roll turn) persist to the OLD session
2. Next message resumes the NEW session → missing recent messages

**Root cause:** `AgentSession` is a single dataclass instance that can't easily "become" a different session.

## Solution

Introduce `SessionState` as a pure data container. `AgentSession` holds a swappable reference to it. On roll, `ContextGuard` returns a new `SessionState`, and `AgentSession` swaps the reference.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AgentSession  │     │  ContextGuard   │     │  SessionState   │
│                 │     │                 │     │                 │
│ - agent         │     │ - shared_context│     │ - session_id    │
│ - state ────────│──┐  │ - threshold     │     │ - agent         │
│ - context_guard │  │  │                 │     │ - messages      │
│ - tools         │  │  │ check_and_compact│────►│ - source        │
│                 │  │  │     (state)     │     │ - shared_context│
│ chat()          │  │  │       ↓         │     │                 │
│ _build_messages()│ │  │   [if rolled]   │     │ add_message()   │
│ _handle_tools() │  │  │       ↓         │     │ get_history()   │
│                 │  │  │  return new_state│     │ _persist()      │
└─────────────────┘  │  └─────────────────┘     └─────────────────┘
                     │           │
                     └───────────┘
                    (swaps on roll)
```

## Components

### SessionState (NEW)

Pure conversation state container with persistence helpers.

```python
@dataclass
class SessionState:
    """Pure conversation state + persistence."""
    session_id: str
    agent: Agent
    messages: list[Message]
    source: EventSource
    shared_context: SharedContext

    def add_message(self, message: Message) -> None:
        """Add message to in-memory list + persist."""
        self.messages.append(message)
        self._persist_message(message)

    def get_history(self) -> list[Message]:
        """Get all messages for LLM context."""
        return self.messages

    def _persist_message(self, message: Message) -> None:
        """Save to HistoryStore."""
        history_msg = HistoryMessage.from_message(message)
        self.shared_context.history_store.save_message(self.session_id, history_msg)
```

### ContextGuard (Updated)

Manages session lifecycle and rolling. Returns new `SessionState` when rolling.

```python
@dataclass
class ContextGuard:
    """Session lifecycle manager."""
    shared_context: SharedContext
    token_threshold: int = 160000

    async def check_and_compact(
        self,
        state: SessionState,
    ) -> tuple[list[Message], SessionState | None]:
        """
        Check token count, compact and roll if needed.

        Args:
            state: Current session state

        Returns:
            - (compacted_messages, new_state) if rolled
            - (original_messages, None) if no roll
        """
        messages = self._build_full_messages(state)
        token_count = self.count_tokens(messages, state.agent.llm.model)

        if token_count < self.token_threshold:
            return messages, None

        return await self._compact_and_roll(state, messages)

    async def _compact_and_roll(
        self,
        state: SessionState,
        messages: list[Message],
    ) -> tuple[list[Message], SessionState]:
        """Compact history, roll to new session, return compacted messages + new state."""
        summary = await self._generate_summary(state, messages)
        new_state = self._roll_session(state)
        compacted_messages = self._build_compacted_messages(summary, messages)
        return compacted_messages, new_state

    def _roll_session(self, state: SessionState) -> SessionState:
        """Create new SessionState, update source mapping."""
        new_session_id = str(uuid.uuid4())

        # Create new session in HistoryStore
        state.shared_context.history_store.create_session(
            state.agent.agent_def.id,
            new_session_id,
            state.source,
        )

        # Update source -> session mapping
        self.shared_context.config.set_runtime(
            f"sources.{state.source}",
            {"session_id": new_session_id},
        )

        # Return new SessionState
        return SessionState(
            session_id=new_session_id,
            agent=state.agent,
            messages=[],
            source=state.source,
            shared_context=state.shared_context,
        )

    def _build_full_messages(self, state: SessionState) -> list[Message]:
        """Build full message list with system prompt."""
        system_prompt = state.shared_context.prompt_builder.build(state)
        messages: list[Message] = [{"role": "system", "content": system_prompt}]
        messages.extend(state.get_history())
        return messages

    # ... existing methods: count_tokens, _generate_summary, _build_compacted_messages, etc.
```

### AgentSession (Updated)

Now a chat orchestrator that operates on swappable `SessionState`.

```python
@dataclass
class AgentSession:
    """Chat orchestrator - operates on swappable SessionState."""

    agent: Agent
    state: SessionState  # Swappable reference
    context_guard: ContextGuard
    tools: ToolRegistry

    async def chat(self, message: str) -> str:
        """Send message to LLM and get response."""
        user_msg: Message = {"role": "user", "content": message}
        self.state.add_message(user_msg)

        tool_schemas = self.tools.get_tool_schemas()

        while True:
            messages = self._build_messages()

            # Check context and compact if needed (may swap state)
            messages, new_state = await self.context_guard.check_and_compact(self.state)
            if new_state:
                self.state = new_state  # Swap to new session!

            content, tool_calls = await self.agent.llm.chat(messages, tool_schemas)

            assistant_msg: Message = {
                "role": "assistant",
                "content": content,
                "tool_calls": [...],
            }
            self.state.add_message(assistant_msg)

            if not tool_calls:
                break

            await self._handle_tool_calls(tool_calls)

        return content

    def _build_messages(self) -> list[Message]:
        """Build messages for LLM API call."""
        system_prompt = self.state.shared_context.prompt_builder.build(self.state)
        messages: list[Message] = [{"role": "system", "content": system_prompt}]
        messages.extend(self.state.get_history())
        return messages

    async def _handle_tool_calls(self, tool_calls: list[LLMToolCall]) -> None:
        """Handle tool calls from LLM response."""
        tool_call_results = await asyncio.gather(
            *[self._execute_tool_call(tc) for tc in tool_calls]
        )

        for tool_call, result in zip(tool_calls, tool_call_results):
            tool_msg: Message = {
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call.id,
            }
            self.state.add_message(tool_msg)

    async def _execute_tool_call(self, tool_call: LLMToolCall) -> str:
        """Execute a single tool call."""
        ...
```

### Agent (Updated)

Creates `SessionState` and wraps it in `AgentSession`.

```python
class Agent:
    def new_session(self, source: EventSource, session_id: str | None = None) -> AgentSession:
        """Create new conversation session."""
        session_id = session_id or str(uuid.uuid4())

        # Build tools
        include_post_message = source.is_cron
        tools = self._build_tools(include_post_message)

        # Create SessionState
        state = SessionState(
            session_id=session_id,
            agent=self,
            messages=[],
            source=source,
            shared_context=self.context,
        )

        # Persist session
        self.context.history_store.create_session(self.agent_def.id, session_id, source)

        # Create ContextGuard
        context_guard = ContextGuard(
            shared_context=self.context,
            token_threshold=self._get_token_threshold(),
        )

        return AgentSession(
            agent=self,
            state=state,
            context_guard=context_guard,
            tools=tools,
        )

    def resume_session(self, session_id: str) -> AgentSession:
        """Load existing conversation session."""
        session_info = self._get_session_info(session_id)
        source = session_info.get_source()

        # Load messages
        history_messages = self.context.history_store.get_messages(session_id)
        messages: list[Message] = [msg.to_message() for msg in history_messages]

        # Build tools
        include_post_message = source.is_cron
        tools = self._build_tools(include_post_message)

        # Reconstruct SessionState
        state = SessionState(
            session_id=session_info.id,
            agent=self,
            messages=messages,
            source=source,
            shared_context=self.context,
        )

        # Create ContextGuard
        context_guard = ContextGuard(
            shared_context=self.context,
            token_threshold=self._get_token_threshold(),
        )

        return AgentSession(
            agent=self,
            state=state,
            context_guard=context_guard,
            tools=tools,
        )
```

## Files Changed

| File | Changes |
|------|---------|
| `core/session_state.py` | **NEW** - SessionState dataclass |
| `core/agent.py` | Split into SessionState + updated AgentSession + updated Agent |
| `core/context_guard.py` | Updated to work with SessionState, return new state on roll |

## Data Flow on Roll

```
1. User sends message
2. AgentSession.chat() adds user message to self.state
3. AgentSession calls context_guard.check_and_compact(self.state)
4. ContextGuard detects over threshold
5. ContextGuard generates summary
6. ContextGuard._roll_session() creates new SessionState with new session_id
7. ContextGuard updates config mapping (sources.{source}.session_id)
8. ContextGuard returns (compacted_messages, new_state)
9. AgentSession does self.state = new_state
10. LLM call proceeds with compacted messages
11. Assistant response added to NEW session (self.state now points to new)
12. Next message resumes new session_id → has all context ✓
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Where messages live | SessionState | Pure data container, swappable |
| Who owns chat loop | AgentSession | Orchestration role, operates on state |
| Who manages lifecycle | ContextGuard | Returns new state on roll |
| Where tools live | AgentSession | Orchestration needs tools for execution |
| Who creates SessionState | Agent | Factory role, has all dependencies |
