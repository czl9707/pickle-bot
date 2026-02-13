import json
import asyncio
from typing import Iterable, TYPE_CHECKING

from litellm.types.completion import (
    ChatCompletionMessageParam as Message,
    ChatCompletionMessageToolCallParam
)
from picklebot.utils.config import AgentConfig
from picklebot.core.session import AgentSession
from picklebot.provider import LLMToolCall, LLMProvider
from picklebot.tools.builtin_tools import register_builtin_tools
from picklebot.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from picklebot.frontend import Frontend

class Agent:
    """
    Main Agent class that handles chat with pluggable LLM providers.

    Supports function calling through the tools system.
    """

    def __init__(
        self,
        config: AgentConfig,
        session: AgentSession,
        frontend: "Frontend",
        llm_provider: LLMProvider,
    ):
        """
        Initialize the agent.

        Args:
            config: Agent configuration
            tool_registry: Tool registry for function calling
            frontend: Frontend for displaying output
            history: Optional history backend for persistence
        """
        self.config = config
        self.session = session
        self.tool_registry = ToolRegistry()
        register_builtin_tools(self.tool_registry)
        self.llm_provider = llm_provider
        self.frontend = frontend

    async def chat(self, message: str) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User message

        Returns:
            Assistant's response text
        """
        user_msg: Message = {"role": "user", "content": message}
        await self.session.add_message(user_msg)

        tools = self.tool_registry.get_tool_schemas()
        tool_count = 0  # Reset tool count for new user input
        display_content = "Thinking"
        
        while True:
            with self.frontend.show_transient(display_content):
                messages = self._build_messages()
                content, tool_calls = await self.llm_provider.chat(messages, tools)
                tool_call_dicts: Iterable[ChatCompletionMessageToolCallParam] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in tool_calls
                ]
                assistant_msg: Message = {"role": "assistant", "content": content, "tool_calls": tool_call_dicts}
                await self.session.add_message(assistant_msg)

                if not tool_calls:
                    break

                await self._handle_tool_calls(tool_calls, content)
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
            {"role": "system", "content": self.config.system_prompt}
        ]
        messages.extend(self.session.get_history(50))

        return messages

    async def _handle_tool_calls(self, tool_calls: list[LLMToolCall], llm_content: str) -> None:
        """
        Handle tool calls from the LLM response.

        Args:
            tool_calls: List of tool calls from LLM response
            llm_content: LLM's text content alongside tool calls
        """

        tool_call_results = await asyncio.gather(
            *[self._execute_tool_call(tool_call, llm_content) for tool_call in tool_calls]
        )

        for tool_call, result in zip(tool_calls, tool_call_results):
            tool_msg: Message = {"role": "tool", "content": result, "tool_call_id": tool_call.id}
            await self.session.add_message(tool_msg)

    async def _execute_tool_call(self, tool_call: LLMToolCall, llm_content: str) -> str:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call from LLM response
            llm_content: LLM's text content alongside tool calls
        """
        # Extract key arguments for display
        try:
            args = json.loads(tool_call.arguments)
        except json.JSONDecodeError:
            args = {}

        tool_display = f"Making Tool Call: {tool_call.name} {tool_call.arguments}"
        if len(tool_display) > 40:
            tool_display = tool_display[:40] + "..."

        with self.frontend.show_transient(tool_display):
            try:
                result = await self.tool_registry.execute_tool(
                    tool_call.name, **args
                )
            except Exception as e:
                result = f"Error executing tool: {e}"

            tool_msg: Message = {"role": "tool", "content": result, "tool_call_id": tool_call.id}
            await self.session.add_message(tool_msg)

            return result
