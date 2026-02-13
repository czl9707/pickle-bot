from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionToolMessageParam,
    ChatCompletionAssistantMessageParam,
)
from picklebot.core.history import HistoryStore, HistoryMessage


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
        tool_calls = None
        if message.get("tool_calls", None):
            message = cast(ChatCompletionAssistantMessageParam, message)
            tool_calls = [
                {
                    "id": tc.get("id"),
                    "type": tc.get("type", "function"),
                    "function": tc.get("function", {}),
                }
                for tc in message.get("tool_calls", [])
            ]

        tool_call_id = None
        if message.get("tool_call_id", None):
            message = cast(ChatCompletionToolMessageParam, message)
            tool_call_id = message.get("tool_call_id")

        history_msg = HistoryMessage(
            role=message["role"],  # type: ignore
            content=str(message.get("content", "")),
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
        )
        self.history_store.save_message(self.session_id, history_msg)
