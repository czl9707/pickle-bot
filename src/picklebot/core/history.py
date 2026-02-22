"""JSONL file-based conversation history backend."""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from litellm.types.completion import ChatCompletionMessageParam as Message

from picklebot.utils.config import Config


def _now_iso() -> str:
    """Return current datetime as ISO format string."""
    return datetime.now().isoformat()


class HistorySession(BaseModel):
    """Session metadata - stored in index.jsonl."""

    id: str
    agent_id: str
    max_history: int = 50  # Maximum messages per chunk
    chunk_count: int = 1  # Number of chunk files
    title: str | None = None
    message_count: int = 0
    created_at: str
    updated_at: str


class HistoryMessage(BaseModel):
    """Single message - stored in session.jsonl."""

    timestamp: str = Field(default_factory=_now_iso)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    @classmethod
    def from_message(cls, message: Message) -> "HistoryMessage":
        """
        Create HistoryMessage from litellm Message format.

        Args:
            message: Message dict from litellm

        Returns:
            New HistoryMessage instance
        """
        # Extract tool_calls from assistant messages
        tool_calls = None
        if message.get("tool_calls"):  # type: ignore[typeddict-item]
            tool_calls = [
                {
                    "id": tc.get("id"),
                    "type": tc.get("type", "function"),
                    "function": tc.get("function", {}),
                }
                for tc in message["tool_calls"]  # type: ignore[typeddict-item]
            ]

        # Extract tool_call_id from tool messages
        tool_call_id = message.get("tool_call_id")  # type: ignore[typeddict-item]

        return cls(
            role=message["role"],  # type: ignore[arg-type]
            content=str(message.get("content", "")),
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,  # type: ignore[arg-type]
        )

    def to_message(self) -> Message:
        """
        Convert HistoryMessage to litellm Message format.

        Returns:
            Message dict compatible with litellm
        """

        # Start with base message
        base: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }

        # Add tool_calls for assistant messages
        if self.role == "assistant" and self.tool_calls:
            # Build the full assistant message with tool_calls
            return {
                "role": "assistant",
                "content": self.content,
                "tool_calls": self.tool_calls,  # type: ignore[typeddict-item]
            }  # type: ignore[return-value]

        # Add tool_call_id for tool messages
        if self.role == "tool" and self.tool_call_id:
            base["tool_call_id"] = self.tool_call_id
            return base  # type: ignore[return-value]

        return base  # type: ignore[return-value]


class HistoryStore:
    """
    JSONL file-based history storage.

    Directory structure:
    ~/.pickle-bot/history/
    ├── index.jsonl              # Session metadata (append-only)
    └── sessions/
        └── session-{id}.jsonl   # Messages (append-only)
    """

    @staticmethod
    def from_config(config: Config) -> "HistoryStore":
        return HistoryStore(config.history_path)

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / "sessions"
        self.index_path = self.base_path / "index.jsonl"

        self.base_path.mkdir(parents=True, exist_ok=True)
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    def _chunk_path(self, session_id: str, index: int) -> Path:
        """Get the file path for a session chunk."""
        return self.sessions_path / f"session-{session_id}.{index}.jsonl"

    def _list_chunks(self, session_id: str) -> list[Path]:
        """List all chunk files for a session, sorted newest first."""
        pattern = f"session-{session_id}.*.jsonl"
        chunks = list(self.sessions_path.glob(pattern))
        # Sort by index (descending - newest first)
        chunks.sort(key=lambda p: int(p.name.split(".")[-2]), reverse=True)
        return chunks

    def _get_current_chunk_index(self, session_id: str) -> int:
        """Get the current (highest) chunk index, or 1 if no chunks exist."""
        chunks = self._list_chunks(session_id)
        if not chunks:
            return 1
        # Extract index from filename: session-id.N.jsonl
        return int(chunks[0].name.split(".")[-2])

    def _count_messages_in_chunk(self, chunk_path: Path) -> int:
        """Count the number of messages in a chunk file."""
        if not chunk_path.exists():
            return 0
        with open(chunk_path) as f:
            return sum(1 for line in f if line.strip())

    def _read_index(self) -> list[HistorySession]:
        """Read all session entries from index.jsonl."""
        if not self.index_path.exists():
            return []

        sessions = []
        with open(self.index_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        sessions.append(HistorySession.model_validate_json(line))
                    except Exception:
                        continue
        return sessions

    def _write_index(self, sessions: list[HistorySession]) -> None:
        """Write all session entries to index.jsonl."""
        with open(self.index_path, "w") as f:
            for session in sessions:
                f.write(session.model_dump_json() + "\n")

    def _find_session_index(
        self, sessions: list[HistorySession], session_id: str
    ) -> int:
        """Find the index of a session in the list."""
        for i, s in enumerate(sessions):
            if s.id == session_id:
                return i
        return -1

    def create_session(
        self, agent_id: str, session_id: str, max_history: int = 50
    ) -> dict[str, Any]:
        """Create a new conversation session."""
        now = _now_iso()
        session = HistorySession(
            id=session_id,
            agent_id=agent_id,
            max_history=max_history,
            chunk_count=1,
            title=None,
            message_count=0,
            created_at=now,
            updated_at=now,
        )

        # Append to index
        with open(self.index_path, "a") as f:
            f.write(session.model_dump_json() + "\n")

        # Create first chunk file
        self._chunk_path(session_id, 1).touch()

        return session.model_dump()

    def save_message(self, session_id: str, message: HistoryMessage) -> None:
        """Save a message to history."""
        # Get session to access max_history
        sessions = self._read_index()
        idx = self._find_session_index(sessions, session_id)
        if idx < 0:
            raise ValueError(f"Session not found: {session_id}")

        session = sessions[idx]
        max_history = session.max_history

        # Get current chunk and check if full
        current_idx = self._get_current_chunk_index(session_id)
        current_chunk = self._chunk_path(session_id, current_idx)
        current_count = self._count_messages_in_chunk(current_chunk)

        # If current chunk is full, create new one
        if current_count >= max_history:
            current_idx += 1
            current_chunk = self._chunk_path(session_id, current_idx)
            session.chunk_count = current_idx

        # Append message to chunk
        with open(current_chunk, "a") as f:
            f.write(message.model_dump_json() + "\n")

        # Update index
        session.message_count += 1
        session.updated_at = _now_iso()

        # Auto-generate title from first user message
        if session.title is None and message.role == "user":
            title = message.content[:50]
            if len(message.content) > 50:
                title += "..."
            session.title = title

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        self._write_index(sessions)

    def update_session_title(self, session_id: str, title: str) -> None:
        """Update a session's title."""
        sessions = self._read_index()
        idx = self._find_session_index(sessions, session_id)
        if idx >= 0:
            sessions[idx].title = title
            sessions[idx].updated_at = _now_iso()
            self._write_index(sessions)
        else:
            raise ValueError(f"Session not found: {session_id}")

    def list_sessions(self) -> list[HistorySession]:
        """List all sessions, most recently updated first."""
        sessions = self._read_index()
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_messages(self, session_id: str) -> list[HistoryMessage]:
        """Get messages for a session, up to max_history."""
        # Get session to access max_history
        sessions = self._read_index()
        idx = self._find_session_index(sessions, session_id)
        if idx < 0:
            return []

        max_history = sessions[idx].max_history

        # Load from chunks, newest first
        chunks = self._list_chunks(session_id)
        messages: list[HistoryMessage] = []

        for chunk in chunks:
            if not chunk.exists():
                continue

            chunk_messages: list[HistoryMessage] = []
            with open(chunk) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            chunk_messages.append(
                                HistoryMessage.model_validate_json(line)
                            )
                        except Exception:
                            continue

            # Prepend older messages
            messages = chunk_messages + messages

            # Stop if we have enough
            if len(messages) >= max_history:
                break

        # Return newest max_history messages
        return messages[-max_history:]
