"""JSON file-based conversation history backend."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import aiofiles
from pydantic import BaseModel, Field


class HistorySession(BaseModel):
    """A conversation session."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    title: str | None = None
    message_count: int = 0
    metadata: dict = Field(default_factory=dict)


class HistoryMessage(BaseModel):
    """A message with full context for history storage."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    agent_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list | None = None
    tool_call_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class SessionIndex(BaseModel):
    """Index entry for session listing."""

    id: str
    agent_id: str
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    message_count: int = 0


class HistoryIndex(BaseModel):
    """Index file structure for fast session listing."""

    sessions: list[SessionIndex] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)


class HistoryStore():
    """
    File-based JSON history storage.

    Directory structure:
    ~/.pickle-bot/history/
    ├── sessions/
    │   ├── session-abc123.json
    │   └── session-def456.json
    └── index.json
    """

    def __init__(self, base_path: Path):
        """
        Initialize the JSON backend.

        Args:
            base_path: Base directory for history storage
        """
        self.base_path = Path(base_path)
        self.sessions_path = self.base_path / "sessions"
        self.index_path = self.base_path / "index.json"
        self._index_cache: HistoryIndex | None = None

    async def _ensure_directories(self) -> None:
        """Ensure storage directories exist."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.sessions_path.mkdir(parents=True, exist_ok=True)

    async def _read_index(self) -> HistoryIndex:
        """Read the session index from disk."""
        if self._index_cache is not None:
            return self._index_cache

        if not self.index_path.exists():
            self._index_cache = HistoryIndex()
            return self._index_cache

        try:
            async with aiofiles.open(self.index_path, "r") as f:
                content = await f.read()
                data = json.loads(content)
                self._index_cache = HistoryIndex.model_validate(data)
                return self._index_cache
        except (json.JSONDecodeError, Exception):
            self._index_cache = HistoryIndex()
            return self._index_cache

    async def _write_index(self, index: HistoryIndex) -> None:
        """Write the session index to disk."""
        await self._ensure_directories()
        index.last_updated = datetime.now()

        async with aiofiles.open(self.index_path, "w") as f:
            await f.write(index.model_dump_json(indent=2))

        self._index_cache = index

    def _session_file_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.sessions_path / f"session-{session_id}.json"

    async def _read_session_file(self, session_id: str) -> dict[str, Any] | None:
        """Read a session file from disk."""
        file_path = self._session_file_path(session_id)

        if not file_path.exists():
            return None

        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        except (json.JSONDecodeError, Exception):
            return None

    async def _write_session_file(self, session_data: dict[str, Any]) -> None:
        """Write a session file to disk."""
        await self._ensure_directories()
        file_path = self._session_file_path(session_data["id"])

        async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(session_data, indent=2, default=str))

    async def create_session(self, agent_id: str, title: str | None = None) -> Session:
        """Create a new conversation session."""
        session = Session(agent_id=agent_id, title=title)

        # Write session file
        session_data: dict[str, Any] = {
            "id": session.id,
            "agent_id": session.agent_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "title": session.title,
            "message_count": 0,
            "metadata": session.metadata,
            "messages": [],
        }
        await self._write_session_file(session_data)

        # Update index
        index = await self._read_index()
        index.sessions.insert(0, SessionIndex(
            id=session.id,
            agent_id=session.agent_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            title=session.title,
            message_count=0,
        ))
        await self._write_index(index)

        return session

    async def save_message(self, message: HistoryMessage) -> None:
        """Save a message to history."""
        session_data = await self._read_session_file(message.session_id)

        if session_data is None:
            raise ValueError(f"Session not found: {message.session_id}")

        # Add message to session
        messages = session_data.get("messages", [])
        messages.append({
            "id": message.id,
            "session_id": message.session_id,
            "agent_id": message.agent_id,
            "timestamp": message.timestamp.isoformat(),
            "role": message.role,
            "content": message.content,
            "tool_calls": message.tool_calls,
            "tool_call_id": message.tool_call_id,
            "metadata": message.metadata,
        })

        # Update session metadata
        session_data["messages"] = messages
        session_data["message_count"] = len(messages)
        session_data["updated_at"] = datetime.now().isoformat()

        # Auto-generate title from first user message
        if session_data.get("title") is None and message.role == "user":
            title = message.content[:50] + ("..." if len(message.content) > 50 else "")
            session_data["title"] = title

        await self._write_session_file(session_data)

        # Update index
        index = await self._read_index()
        for session_entry in index.sessions:
            if session_entry.id == message.session_id:
                session_entry.message_count = len(messages)
                session_entry.updated_at = datetime.now()
                if session_data.get("title"):
                    session_entry.title = session_data["title"]
                break
        await self._write_index(index)

    async def get_session_messages(
        self,
        session_id: str,
        limit: int | None = None
    ) -> list[HistoryMessage]:
        """Get all messages for a session."""
        session_data = await self._read_session_file(session_id)

        if session_data is None:
            return []

        messages = session_data.get("messages", [])

        # Apply limit (get most recent)
        if limit is not None:
            messages = messages[-limit:]

        return [
            HistoryMessage(
                id=msg["id"],
                session_id=msg["session_id"],
                agent_id=msg["agent_id"],
                timestamp=datetime.fromisoformat(msg["timestamp"]),
                role=msg["role"],
                content=msg["content"],
                tool_calls=msg.get("tool_calls"),
                tool_call_id=msg.get("tool_call_id"),
                metadata=msg.get("metadata", {}),
            )
            for msg in messages
        ]

    async def search_messages(
        self,
        query: str,
        agent_id: str | None = None,
        limit: int = 50
    ) -> list[HistoryMessage]:
        """Search messages by content (simple text matching)."""
        results: list[HistoryMessage] = []
        query_lower = query.lower()

        index = await self._read_index()

        # Search through sessions
        for session_entry in index.sessions:
            if agent_id and session_entry.agent_id != agent_id:
                continue

            messages = await self.get_session_messages(session_entry.id)

            for msg in messages:
                if query_lower in msg.content.lower():
                    results.append(msg)
                    if len(results) >= limit:
                        return results

        return results

    async def list_sessions(
        self,
        agent_id: str | None = None,
        limit: int = 20
    ) -> list[Session]:
        """List recent sessions."""
        index = await self._read_index()

        sessions: list[Session] = []
        for entry in index.sessions:
            if agent_id and entry.agent_id != agent_id:
                continue

            sessions.append(Session(
                id=entry.id,
                agent_id=entry.agent_id,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                title=entry.title,
                message_count=entry.message_count,
            ))

            if len(sessions) >= limit:
                break

        return sessions

    async def get_session(self, session_id: str) -> Session | None:
        """Get a specific session by ID."""
        session_data = await self._read_session_file(session_id)

        if session_data is None:
            return None

        return Session(
            id=session_data["id"],
            agent_id=session_data["agent_id"],
            created_at=datetime.fromisoformat(session_data["created_at"]),
            updated_at=datetime.fromisoformat(session_data["updated_at"]),
            title=session_data.get("title"),
            message_count=session_data.get("message_count", 0),
            metadata=session_data.get("metadata", {}),
        )

    async def update_session_title(self, session_id: str, title: str) -> None:
        """Update a session's title."""
        session_data = await self._read_session_file(session_id)

        if session_data is None:
            raise ValueError(f"Session not found: {session_id}")

        session_data["title"] = title
        session_data["updated_at"] = datetime.now().isoformat()

        await self._write_session_file(session_data)

        # Update index
        index = await self._read_index()
        for session_entry in index.sessions:
            if session_entry.id == session_id:
                session_entry.title = title
                session_entry.updated_at = datetime.now()
                break
        await self._write_index(index)
