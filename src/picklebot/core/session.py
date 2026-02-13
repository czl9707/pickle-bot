from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from uuid import uuid4

from litellm.types.completion import (
    ChatCompletionMessageParam as Message, 
    ChatCompletionToolMessageParam, 
    ChatCompletionAssistantMessageParam
)
from picklebot.utils.config import AgentConfig
from .history import HistoryStore, HistoryMessage


@dataclass
class AgentSession:
    """
    Runtime state for the pickle-bot agent.
    """

    agent_config: AgentConfig
    history_store: "HistoryStore"
    session_id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    async def __aenter__(self):
        # ensure history_store initialize the session.
        await self.history_store.create_session(self.agent_config.name, self.session_id)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # update session name.
        self.history_store

    async def add_message(self, message: Message) -> None:
        """Add a message to the conversation history."""
        self.messages.append(message)
        await self._save_message_to_history(message)

    def get_history(self, max_messages: int = 50) -> list[Message]:
        """
        Get conversation history.

        Args:
            max_messages: Maximum number of messages to return

        Returns:
            List of messages in litellm format
        """
        return self.messages[-max_messages:]

    async def _save_message_to_history(self, message: Message) -> None:
        """
        Persist a message to the history backend.

        Args:
            message: The message to persist (in litellm format)
        """

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
            tool_calls = tool_calls,
            tool_call_id=tool_call_id,
        )
        await self.history_store.save_message(history_msg)
