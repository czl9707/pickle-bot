"""Session state container with persistence helpers."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from litellm.types.completion import ChatCompletionMessageParam as Message

from picklebot.core.history import HistoryMessage

if TYPE_CHECKING:
    from picklebot.core.agent import Agent
    from picklebot.core.context import SharedContext
    from picklebot.core.events import EventSource


@dataclass
class SessionState:
    """Pure conversation state + persistence."""

    session_id: str
    agent: "Agent"
    messages: list[Message]
    source: "EventSource"
    shared_context: "SharedContext"

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
