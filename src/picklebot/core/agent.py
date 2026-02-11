import json
import asyncio
from typing import Any, Iterable

from litellm.types.completion import (
    ChatCompletionMessageParam as Message, 
    ChatCompletionMessageToolCallParam
)
from picklebot.config import Config
from picklebot.core.state import AgentState
from picklebot.provider import LLMToolCall, LLMProvider
from picklebot.tools.registry import ToolRegistry


class Agent:
    """
    Main Agent class that handles chat with pluggable LLM providers.

    Supports function calling through the tools system.
    """

    def __init__(self, config: Config, tool_registry: ToolRegistry | None = None):
        """
        Initialize the agent.

        Args:
            config: Agent configuration
            tool_registry: Optional tool registry for function calling
        """
        self.config = config
        self.state = AgentState()
        self._tool_registry = tool_registry
        self._llm_provider = LLMProvider.from_config(config.llm)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """
        Get tool schemas from the tool registry.

        Returns:
            List of tool/function schemas
        """
        if self._tool_registry is None:
            return []

        return self._tool_registry.get_tool_schemas()

    async def chat(self, message: str) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User message

        Returns:
            Assistant's response text
        """
        self.state.add_message({"role": "user", "content": message})
        tools = self.get_tool_schemas() if self._tool_registry else None

        while True:
            messages = self._build_messages()
            content, tool_calls = await self._llm_provider.chat(messages, tools)
            tool_call_dicts: Iterable[ChatCompletionMessageToolCallParam] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]
            self.state.add_message({"role": "assistant", "content": content, "tool_calls": tool_call_dicts})
            
            if not tool_calls:
                break

            await self._handle_tool_calls(tool_calls)
            continue

        return content

    def _build_messages(self) -> list[Message]:
        """
        Build messages for LLM API call.

        Returns:
            List of messages compatible with litellm
        """
        messages: list[Message] = [
            {"role": "system", "content": self.config.agent.system_prompt}
        ]
        messages.extend(self.state.get_history(50))

        return messages

    async def _handle_tool_calls(self, tool_calls: list[LLMToolCall]) -> None:
        """
        Handle tool calls from the LLM response.

        Args:
            response: LLM response with tool calls
            messages: Current conversation messages

        Returns:
            Final assistant response text
        """
        
        tool_call_results = await asyncio.gather(
            *[self._execute_tool_call(tool_call) for tool_call in tool_calls]
        )

        for tool_call, result in zip(tool_calls, tool_call_results):
            self.state.add_message(
                {"role": "tool", "content": result, "tool_call_id": tool_call.id}
            )

    async def _execute_tool_call(self, tool_call: LLMToolCall) -> str:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call from LLM response
        """
        if self._tool_registry is None:
            result = "Error: No tool registry available"
        else:
            try:
                args = json.loads(tool_call.arguments)
                result = await self._tool_registry.execute_tool(
                    tool_call.name, **args
                )
            except Exception as e:
                result = f"Error executing tool: {e}"

        self.state.add_message(
            {"role": "tool", "content": result, "tool_call_id": tool_call.id}
        )

        return result
