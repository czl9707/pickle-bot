import uuid
import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from typing import TYPE_CHECKING

from picklebot.core.context import SharedContext
from picklebot.provider import LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.tools.skill_tool import create_skill_tool
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.core.history import HistoryMessage

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionMessageToolCallParam,
)


if TYPE_CHECKING:
    from picklebot.core.agent_loader import AgentDef
    from picklebot.frontend import Frontend
    from picklebot.provider import LLMToolCall


class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM, tools, and config
    that sessions use for chatting.
    """

    def __init__(self, agent_def: "AgentDef", context: SharedContext) -> None:
        self.agent_def = agent_def
        self.context = context
        # tools currently is initialized within Agent class.
        # This is intentional, in case agent will have its own tool regitry config later.
        self.tools = ToolRegistry.with_builtins()
        self.llm = LLMProvider.from_config(agent_def.llm)

        # Add skill tool if allowed
        if agent_def.allow_skills:
            self._register_skill_tool()

        # Add subagent dispatch tool
        self._register_subagent_tool()

    def _register_skill_tool(self) -> None:
        """Register the skill tool if skills are available."""
        skill_tool = create_skill_tool(self.context.skill_loader)
        if skill_tool:
            self.tools.register(skill_tool)

    def _register_subagent_tool(self) -> None:
        """Register the subagent dispatch tool if agents are available."""
        subagent_tool = create_subagent_dispatch_tool(self.agent_def.id, self.context)
        if subagent_tool:
            self.tools.register(subagent_tool)

    def new_session(self) -> "AgentSession":
        """
        Create a new conversation session.

        Returns:
            A new Session instance with self as the agent reference.
        """
        session_id = str(uuid.uuid4())
        session = AgentSession(
            session_id=session_id,
            agent_id=self.agent_def.id,
            context=self.context,
            agent=self,
        )

        self.context.history_store.create_session(self.agent_def.id, session_id)
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
            session
            for session in self.context.history_store.list_sessions()
            if session.id == session_id
        ]
        if not session_query:
            raise ValueError(f"Session not found: {session_id}")

        session_info = session_query[0]
        history_messages = self.context.history_store.get_messages(session_id)

        # Convert HistoryMessage to litellm Message format
        messages: list[Message] = [msg.to_message() for msg in history_messages]

        return AgentSession(
            session_id=session_info.id,
            agent_id=session_info.agent_id,
            context=self.context,
            agent=self,
            messages=messages,
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
        history_msg = HistoryMessage.from_message(message)
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
                assistant_msg: Message = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_call_dicts,
                }

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
            {"role": "system", "content": self.agent.agent_def.system_prompt}
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
