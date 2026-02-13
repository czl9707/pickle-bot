import json
import asyncio
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionMessageToolCallParam,
)

from picklebot.core.context import SharedContext
from picklebot.core.session import Session
from picklebot.provider import LLMToolCall, LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import AgentConfig

if TYPE_CHECKING:
    from picklebot.frontend import Frontend


@dataclass
class Agent:
    """
    Main Agent class that handles chat with pluggable LLM providers.

    Supports function calling through the tools system.
    Agent is reusable across multiple sessions.
    """

    agent_config: AgentConfig
    llm: LLMProvider
    tools: ToolRegistry
    context: SharedContext

    def new_session(self) -> Session:
        """
        Create a new conversation session.

        Returns:
            A new Session instance registered with this agent.
        """
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            agent_id=self.agent_config.name,
            history_store=self.context.history_store,
        )
        # Create session in history store
        self.context.history_store.create_session(self.agent_config.name, session_id)
        return session

    async def chat(self, session: Session, message: str, frontend: "Frontend") -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            session: The conversation session
            message: User message
            frontend: Frontend for displaying output

        Returns:
            Assistant's response text
        """
        user_msg: Message = {"role": "user", "content": message}
        session.add_message(user_msg)

        tool_schemas = self.tools.get_tool_schemas()
        tool_count = 0
        display_content = "Thinking"

        while True:
            with frontend.show_transient(display_content):
                messages = self._build_messages(session)
                content, tool_calls = await self.llm.chat(messages, tool_schemas)

                tool_call_dicts: list[ChatCompletionMessageToolCallParam] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in tool_calls
                ]
                assistant_msg: Message = {"role": "assistant", "content": content, "tool_calls": tool_call_dicts}


                session.add_message(assistant_msg)

                if not tool_calls:
                    break

                await self._handle_tool_calls(session, tool_calls, content, frontend)
                tool_count += len(tool_calls)

                display_content = f"{content}\n - Total Tools Used: {tool_count}"

                continue

        return content

    def _build_messages(self, session: Session) -> list[Message]:
        """
        Build messages for LLM API call.

        Args:
            session: The conversation session

        Returns:
            List of messages compatible with litellm
        """
        messages: list[Message] = [
            {"role": "system", "content": self.agent_config.system_prompt}
        ]
        messages.extend(session.get_history(50))

        return messages

    async def _handle_tool_calls(
        self,
        session: Session,
        tool_calls: list[LLMToolCall],
        llm_content: str,
        frontend: "Frontend",
    ) -> None:
        """
        Handle tool calls from the LLM response.

        Args:
            session: The conversation session
            tool_calls: List of tool calls from LLM response
            llm_content: LLM's text content alongside tool calls
            frontend: Frontend for displaying output
        """
        tool_call_results = await asyncio.gather(
            *[
                self._execute_tool_call(session, tool_call, llm_content, frontend)
                for tool_call in tool_calls
            ]
        )

        for tool_call, result in zip(tool_calls, tool_call_results):
            tool_msg: Message = {
                "role": "tool",
                "content": result,
                "tool_call_id": tool_call.id,
            }
            session.add_message(tool_msg)

    async def _execute_tool_call(
        self,
        session: Session,
        tool_call: LLMToolCall,
        llm_content: str,
        frontend: "Frontend",
    ) -> str:
        """
        Execute a single tool call.

        Args:
            session: The conversation session
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
                result = await self.tools.execute_tool(tool_call.name, **args)
            except Exception as e:
                result = f"Error executing tool: {e}"

            return result
