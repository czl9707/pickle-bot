"""Agent state management for pickle-bot."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Message:
    """A message in the conversation history."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentState:
    """
    Runtime state for the pickle-bot agent.

    For MVP, conversation history is kept in-memory.
    """

    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add a message to the conversation history."""
        message = Message(role=role, content=content, **kwargs)
        self.messages.append(message)

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get conversation history in LiteLLM format.

        Args:
            max_messages: Maximum number of messages to return

        Returns:
            List of message dictionaries for LiteLLM
        """
        recent = self.messages[-max_messages:] if max_messages else self.messages

        history = []
        for msg in recent:
            msg_dict = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.tool_call_id is not None:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls is not None:
                msg_dict["tool_calls"] = msg.tool_calls
            history.append(msg_dict)

        return history

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.messages.clear()
