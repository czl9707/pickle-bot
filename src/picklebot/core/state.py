from dataclasses import dataclass, field
from datetime import datetime

from litellm.types.completion import ChatCompletionMessageParam as Message


@dataclass
class AgentState:
    """
    Runtime state for the pickle-bot agent.

    For MVP, conversation history is kept in-memory.
    """

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

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.messages.clear()
