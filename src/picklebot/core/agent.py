import uuid
import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from typing import TYPE_CHECKING, cast

from picklebot.core.context import SharedContext
from picklebot.provider import LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import AgentConfig
from picklebot.core.history import HistoryMessage

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionToolMessageParam,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageToolCallParam,
)


if TYPE_CHECKING:
    from picklebot.frontend import Frontend
    from picklebot.provider import LLMToolCall

@dataclass
class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM, tools, and config
    that sessions use for chatting.
    """

    agent_config: AgentConfig
    llm: LLMProvider
    tools: ToolRegistry
    context: SharedContext

    def new_session(self) -> "AgentSession":
        """
        Create a new conversation session.

        Returns:
            A new Session instance with self as the agent reference.
        """
        session_id = str(uuid.uuid4())
        session = AgentSession(
            session_id=session_id,
            agent_id=self.agent_config.name,
            context=self.context,
            agent=self,
        )

        self.context.history_store.create_session(self.agent_config.name, session_id)
        return session

    def resume_session(self, session_id: str) -> "AgentSession":
        """
        Load an existing conversation session.

        Args:
            session_id: The ID of the session to load.

        Returns:
            A Session instance with self as the agent reference.
        """
        session_query = [
            session for session in
            self.context.history_store.list_sessions()
            if session.id == session_id
        ]
        if not session_query:
            raise ValueError(f"Session not found: {session_id}")
        
        session_info = session_query[0]
        return AgentSession(
            session_id=session_info.id,
            agent_id=session_info.agent_id,
            context=self.context,
            agent=self,
            messages=self.context.history_store.get_messages(session_id),
        )


@dataclass
class AgentSession:
    """Runtime state for a single conversation."""

    session_id: str
    agent_id: str
    context: SharedContext
    agent: Agent  # Reference to parent agent for LLM/tools access

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
        self.context.history_store.save_message(self.session_id, history_msg)

    async def chat(self, message: str, frontend: "Frontend") -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User message
            frontend: Frontend for displaying output

        Returns:
            Assistant's response text
        """
        user_msg: Message = {"role": "user", "content": message}
        self.add_message(user_msg)

        tool_schemas = self.agent.tools.get_tool_schemas()
        tool_count = 0
        display_content = "Thinking"

        while True:
            with frontend.show_transient(display_content):
                messages = self._build_messages()
                content, tool_calls = await self.agent.llm.chat(messages, tool_schemas)

                tool_call_dicts: list[ChatCompletionMessageToolCallParam] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in tool_calls
                ]
                assistant_msg: Message = {"role": "assistant", "content": content, "tool_calls": tool_call_dicts}

                self.add_message(assistant_msg)

                if not tool_calls:
                    break

                await self._handle_tool_calls(tool_calls, content, frontend)
                tool_count += len(tool_calls)

                display_content = f"{content}\n - Total Tools Used: {tool_count}"

                continue

        return content

    def _build_messages(self) -> list[Message]:
        """
        Build messages for LLM API call.

        Returns:
            List of messages compatible with litellm
        """
        messages: list[Message] = [
            {"role": "system", "content": self.agent.agent_config.system_prompt}
        ]
        messages.extend(self.get_history(50))

        return messages

    async def _handle_tool_calls(
        self,
        tool_calls: list["LLMToolCall"],
        llm_content: str,
        frontend: "Frontend",
    ) -> None:
        """
        Handle tool calls from the LLM response.

        Args:
            tool_calls: List of tool calls from LLM response
            llm_content: LLM's text content alongside tool calls
            frontend: Frontend for displaying output
        """
        tool_call_results = await asyncio.gather(
            *[
                self._execute_tool_call(tool_call, llm_content, frontend)
                for tool_call in tool_calls
            ]
        )

        for tool_call, result in zip(tool_calls, tool_call_results):
            tool_msg: Message = {
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call.id,
            }
            self.add_message(tool_msg)

    async def _execute_tool_call(
        self,
        tool_call: "LLMToolCall",
        llm_content: str,
        frontend: "Frontend",
    ) -> str:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call from LLM response
            llm_content: LLM's text content alongside tool calls
            frontend: Frontend for displaying output

        Returns:
            Tool execution result
        """
        # Extract key arguments for display
        try:
            args = json.loads(tool_call.arguments)
        except json.JSONDecodeError:
            args = {}

        tool_display = f"Making Tool Call: {tool_call.name} {tool_call.arguments}"
        if len(tool_display) > 40:
            tool_display = tool_display[:40] + "..."

        with frontend.show_transient(tool_display):
            try:
                result = await self.agent.tools.execute_tool(tool_call.name, **args)
            except Exception as e:
                result = f"Error executing tool: {e}"

            return result
