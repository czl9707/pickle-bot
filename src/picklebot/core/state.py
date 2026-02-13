from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from litellm.types.completion import ChatCompletionMessageParam as Message

if TYPE_CHECKING:
    from .history import HistoryStore, HistoryMessage


@dataclass
class AgentState:
    """
    Runtime state for the pickle-bot agent.
    """

    agent_id: str
    session: "Session"
    history_store: "HistoryStore"
    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)

    def get_history(self, max_messages: int = 50) -> list[Message]:
        """
        Get conversation history.

        Args:
            max_messages: Maximum number of messages to return

        Returns:
            List of messages in litellm format
        """
        return self.messages[-max_messages:]

    def set_history(self, history: "HistoryStore", agent_id: str) -> None:
        """
        Configure history backend for persistence.

        Args:
            history: The history backend to use
            agent_id: ID of the agent (from config)
        """
        self.history_store = history
        self.agent_id = agent_id

    async def initialize_session(self) -> None:
        """Create a new session in the history backend."""
        if self.history_store and not self.session:
            self.session = await self.history_store.create_session(self.agent_id)

    async def save_message_to_history(self, message: Message) -> None:
        """
        Persist a message to the history backend.

        Args:
            message: The message to persist (in litellm format)
        """
        if self.history_store and self.session:

            # Extract content safely
            content = ""
            if isinstance(message.get("content"), str):
                content = message["content"]
            elif message.get("content") is not None:
                content = str(message["content"])

            # Convert tool_calls to serializable format
            tool_calls = None
            if message.get("tool_calls"):
                tool_calls = [
                    {
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": tc.get("function", {}),
                    }
                    for tc in message["tool_calls"]
                ]

            history_msg = HistoryMessage(
                session_id=self.session.id,
                agent_id=self.agent_id,
                role=message["role"],  # type: ignore
                content=content,
                tool_calls=tool_calls,
                tool_call_id=message.get("tool_call_id"),
            )
            await self.history_store.save_message(history_msg)
