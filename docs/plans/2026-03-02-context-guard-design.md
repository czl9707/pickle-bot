# Context Guard with Session Rolling - Design

> Proactive token-aware context management with seamless session handoff.

## Overview

Replace the current message-count-based history limiting with a token-aware context guard that proactively compacts conversation history and rolls to a new session when approaching model context limits.

**Key behaviors:**
- Transparent handoff - user continues chatting without noticing
- Token-aware compaction using LiteLLM's token_counter
- Roll to-new session on compaction with automatic source routing update
- Archive old sessions (keep for audit/debugging)
- Remove all max_history and chunking logic

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentSession                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ chat()                                               │    │
│  │  ├── _build_messages()                               │    │
│  │  ├── context_guard.check_and_compact(messages) ────►│    │
│  │  │   └── if over threshold:                          │    │
│  │  │       ├── compact_history() → summary             │    │
│  │  │       ├── roll_to_new_session()                   │    │
│  │  │       └── return new messages                     │    │
│  │  └── llm.chat(messages)                              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     ContextGuard                             │
│  - token_threshold: int (e.g., 160k for 200k context)       │
│  - check_and_compact(messages) → messages                   │
│  - compact_history(messages) → summary + recent messages    │
│  - roll_session(session, summary) → new_session_id          │
│  - count_tokens(messages) → int                             │
└─────────────────────────────────────────────────────────────┘
```

## Components

### ContextGuard Class

```python
class ContextGuard:
    """Manages context window size with proactive compaction."""

    def __init__(
        self,
        shared_context: SharedContext,
        token_threshold: int = 160000
    ):
        self.shared_context = shared_context
        self.token_threshold = token_threshold

    def count_tokens(self, messages: list[Message], model: str) -> int:
        """Count tokens using litellm's token_counter."""
        return token_counter(model=model, messages=messages)

    def check_and_compact(
        self,
        session: AgentSession,
        messages: list[Message]
    ) -> list[Message]:
        """Check token count, compact and roll session if needed."""
        token_count = self.count_tokens(messages, session.agent.llm.model)

        if token_count < self.token_threshold:
            return messages

        # Compact and roll
        return self._compact_and_roll(session, messages)

    def _compact_and_roll(
        self,
        session: AgentSession,
        messages: list[Message]
    ) -> list[Message]:
        """Compact history, roll to new session, return new messages."""
        # 1. Generate summary of older messages
        summary = await self._generate_summary(session, messages)

        # 2. Create new session with summary injected
        new_session_id = self._roll_session(session, summary)

        # 3. Return messages: [summary_user, summary_assistant] + recent
        return self._build_compacted_messages(summary, messages)

    def _roll_session(self, session: AgentSession, summary: str) -> str:
        """Create new session, update source mapping, return new ID."""
        # Create new session
        new_session = session.agent.new_session(session.source)

        # Inject summary as initial context
        # Update source → session mapping
        self.shared_context.config.set_runtime(
            f"sources.{session.source}",
            {"session_id": new_session.session_id}
        )

        return new_session.session_id
```

### History Compaction Logic

**Compaction strategy:**
- Keep most recent 20% of messages (4+ messages)
- Compress oldest 50% via LLM summary
- Replace with `[summary_user, summary_assistant]` pair + recent messages

```python
def _generate_summary(
    self,
    session: AgentSession,
    messages: list[Message]
) -> str:
    """Generate summary of older messages using agent's LLM."""
    keep_count = max(4, int(len(messages) * 0.2))
    compress_count = max(2, int(len(messages) * 0.5))
    compress_count = min(compress_count, len(messages) - keep_count)

    old_messages = messages[:compress_count]

    # Serialize old messages for summary
    old_text = self._serialize_messages_for_summary(old_messages)
    summary_prompt = f"""Summarize the conversation so far. Keep it factual and concise. Focus on key decisions, facts, and user preferences discovered:

{old_text}"""

    # Use agent's LLM to generate summary
    response = await session.agent.llm.chat(
        [{"role": "user", "content": summary_prompt}],
        []
    )
    return response

def _build_compacted_messages(
    self,
    summary: str,
    original_messages: list[Message]
) -> list[Message]:
    """Build new message list with summary + recent messages."""
    keep_count = max(4, int(len(original_messages) * 0.2))
    compress_count = min(
        int(len(original_messages) * 0.5),
        len(original_messages) - keep_count
    )

    return [
        {"role": "user", "content": f"[Previous conversation summary]\n{summary}"},
        {"role": "assistant", "content": "Understood, I have the context."},
    ] + original_messages[compress_count:]
```

### AgentSession Changes

1. **Remove `max_history` field** - no longer needed with token-aware approach
2. **Add `context_guard` reference** - injected from Agent
3. **Update `chat()` to check context before LLM call**

```python
@dataclass
class AgentSession:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    shared_context: SharedContext
    agent: Agent
    tools: ToolRegistry
    source: EventSource
    # REMOVED: max_history

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    context_guard: ContextGuard = field(init=False)  # Added

    async def chat(self, message: str) -> str:
        user_msg: Message = {"role": "user", "content": message}
        self.add_message(user_msg)

        tool_schemas = self.tools.get_tool_schemas()

        while True:
            messages = self._build_messages()

            # NEW: Check context and compact if needed
            messages = self.context_guard.check_and_compact(self, messages)

            content, tool_calls = await self.agent.llm.chat(
                messages, tool_schemas
            )
            # ... rest unchanged
```

### HistoryStore Simplification

**Remove chunking logic** - one JSONL file per session, no size limits.

```python
class HistoryStore:
    """JSONL file-based history storage - simplified."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / "sessions"
        self.index_path = self.base_path / "index.jsonl"
        # REMOVED: max_history_file_size

    def _session_path(self, session_id: str) -> Path:
        """Single file per session."""
        return self.sessions_path / f"{session_id}.jsonl"

    # REMOVED: _chunk_path, _list_chunks, _get_current_chunk_index,
    #          _count_messages_in_chunk

    def create_session(self, agent_id: str, session_id: str, source: EventSource) -> dict:
        session = HistorySession(
            id=session_id,
            agent_id=agent_id,
            source=source,
            # REMOVED: chunk_count
            title=None,
            message_count=0,
            created_at=now,
            updated_at=now,
        )
        # Create session file (no chunking)
        self._session_path(session_id).touch()
        ...

    def save_message(self, session_id: str, message: HistoryMessage) -> None:
        # Simply append to single file
        session_file = self._session_path(session_id)
        with open(session_file, "a") as f:
            f.write(message.model_dump_json() + "\n")
        # Update index...

    def get_messages(self, session_id: str) -> list[HistoryMessage]:
        """Get all messages for a session - token limiting handled by ContextGuard."""
        # REMOVED: max_history parameter
        session_file = self._session_path(session_id)
        messages = []
        with open(session_file) as f:
            for line in f:
                if line.strip():
                    messages.append(HistoryMessage.model_validate_json(line))
        return messages
```

**Also remove from `HistorySession`:**
- `chunk_count` field

**Remove from `Config`:**
- `max_history_file_size` config option

## Data Flow

```
  Telegram/Discord          ChannelWorker
       │                         │
       │  message + source      │
       └────────────────────────►│
                               │
                               │ _get_or_create_session_id()
                               │   ┌─────────────────────────────┐
                               │   │ Check sources.{src} config   │
                               │   │ If exists → return session_id│
                               │   │ If not → create new session  │
                               │   └─────────────────────────────┘
                               │
                               ▼
                          InboundEvent
                               │
                               ▼
                          AgentWorker
                               │
                               │ agent.resume_session(session_id)
                               ▼
                          AgentSession.chat(message)
                               │
                               │ _build_messages()
                               │
                               │ context_guard.check_and_compact()
                               │   ┌─────────────────────────────────────┐
                               │   │ Count tokens                          │
                               │   │ If under threshold → return messages │
                               │   │ If over threshold:                    │
                               │   │   ├── Generate summary (LLM)          │
                               │   │   ├── Create new session              │
                               │   │   ├── Update sources.{src}.session_id │
                               │   │   └── Return compacted messages        │
                               │   └─────────────────────────────────────┘
                               │
                               ▼
                          LLM Response
                               │
                               ▼
                          OutboundEvent
                               │
                               ▼
                          DeliveryWorker → Platform
```

**Key insight:** The source-to-session mapping in config is the source of truth. When compaction rolls to a new session, the mapping updates, so the next inbound message automatically routes to the new session.

## Files Changed

| File | Changes |
|------|---------|
| `core/context_guard.py` | **NEW** - ContextGuard class |
| `core/agent.py` | Add ContextGuard integration, remove max_history, remove get_source_settings() |
| `core/history.py` | Remove chunking, simplify HistorySession and HistoryStore |
| `utils/config.py` | Remove max_history_file_size config |
| `server/channels_worker.py` | No changes needed |
| `server/agent_worker.py` | No changes needed |

## Removed

- `max_history` field from AgentSession
- `max_history_file_size` from Config
- `chunk_count` from HistorySession
- All chunking methods from HistoryStore (`_chunk_path`, `_list_chunks`, `_get_current_chunk_index`, `_count_messages_in_chunk`)
- `get_source_settings()` function from agent.py

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Handoff style | Transparent | User continues without interruption |
| Compaction trigger | Proactive token-aware | Prevents API errors, better UX |
| Token counting | LiteLLM token_counter | Already in project, handles multiple models |
| Summary model | Same as agent | Simple, consistent |
| Old session handling | Archive | Keep for audit/debugging |
| Truncation stage | Skipped | Proactive compaction handles most cases |
| History chunking | Removed | Simpler, sessions roll on compaction anyway |
