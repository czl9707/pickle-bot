"""Session resource router."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryMessage, HistorySession

router = APIRouter()


class SessionResponse(BaseModel):
    """Response model for session with messages."""

    id: str
    agent_id: str
    title: str | None
    message_count: int
    created_at: str
    updated_at: str
    messages: list[HistoryMessage]


@router.get("", response_model=list[HistorySession])
def list_sessions(ctx: SharedContext = Depends(get_context)) -> list[HistorySession]:
    """List all sessions."""
    return ctx.history_store.list_sessions()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, ctx: SharedContext = Depends(get_context)) -> dict:
    """Get session by ID with messages."""
    sessions = ctx.history_store.list_sessions()
    session = next((s for s in sessions if s.id == session_id), None)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    messages = ctx.history_store.get_messages(session_id)

    return {
        "id": session.id,
        "agent_id": session.agent_id,
        "title": session.title,
        "message_count": session.message_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": messages,
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete a session."""
    session_file = ctx.history_store._session_file_path(session_id)

    if not session_file.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Remove session file
    session_file.unlink()

    # Remove from index
    sessions = ctx.history_store._read_index()
    sessions = [s for s in sessions if s.id != session_id]
    ctx.history_store._write_index(sessions)
