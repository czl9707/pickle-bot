"""JSON file-based conversation history backend."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import aiofiles
from pydantic import BaseModel, Field

from picklebot.utils.config import Config


class HistorySession(BaseModel):
    """A conversation session."""

    id: str
    agent_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    title: str | None = None
    message_count: int = 0


class HistoryMessage(BaseModel):
    """A message with full context for history storage."""

    timestamp: datetime = Field(default_factory=datetime.now)
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

class HistoryIndex(BaseModel):
    """Index file structure for fast session listing."""

    sessions: list[HistorySession] = Field(default_factory=list)
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

    @staticmethod
    def from_config(config: Config) -> "HistoryStore":
        return HistoryStore(config.workspace / config.history.path)

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
        file_path = self._session_file_path(session_data["id"])

        async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(session_data, indent=2, default=str))

    async def create_session(self, agent_id: str, session_id: str) -> HistorySession:
        """Create a new conversation session."""
        session = HistorySession(agent_id=agent_id, id=session_id)

        session_data: dict[str, Any] = {
            "id": session.id,
            "agent_id": session.agent_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "title": session.title,
            "message_count": 0,
            "messages": [],
        }
        await self._write_session_file(session_data)

        index = await self._read_index()
        index.sessions.insert(0, HistorySession(
            id=session.id,
            agent_id=session.agent_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            title=session.title,
            message_count=0,
        ))
        await self._write_index(index)

        return session

    async def save_message(self, session_id: str, message: HistoryMessage) -> None:
        """Save a message to history."""
        session_data = await self._read_session_file(session_id)

        if session_data is None:
            raise ValueError(f"Session not found: {session_id}")

        messages = session_data.get("messages", [])
        messages.append({
            "timestamp": message.timestamp.isoformat(),
            "role": message.role,
            "content": message.content,
            "tool_call_id": message.tool_call_id,
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
            if session_entry.id == session_id:
                session_entry.message_count = len(messages)
                session_entry.updated_at = datetime.now()
                if session_data.get("title"):
                    session_entry.title = session_data["title"]
                break
        await self._write_index(index)

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
