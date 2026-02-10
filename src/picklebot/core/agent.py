import json
from typing import Any

from litellm.types.completion import ChatCompletionMessageParam as Message

from picklebot.config import Config
from picklebot.core.state import AgentState
from picklebot.provider import LLMToolCall, LLMProvider


class Agent:
    """
    Main Agent class that handles chat with pluggable LLM providers.

    Supports function calling through the tools system.
    """

    def __init__(self, config: Config):
        """
        Initialize the agent.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.state = AgentState()
        self._tool_registry = None  # Will be set by the CLI or explicitly
        self._llm_provider = LLMProvider.from_config(config.llm)

    def set_tool_registry(self, registry) -> None:
        """Set the tool registry for function calling."""
        self._tool_registry = registry

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
        # Add user message to history
        self.state.add_message({"role": "user", "content": message})

        # Build messages for LLM
        messages = self._build_messages()

        # Get tool schemas
        tools = self.get_tool_schemas() if self._tool_registry else None

        # Call LLM provider
        response = await self._llm_provider.chat(messages, tools)

        # Handle tool calls
        if response.tool_calls:
            return await self._handle_tool_calls(response, messages)

        # No tool calls, save and return content
        self.state.add_message({"role": "assistant", "content": response.content})
        return response.content

    def _build_messages(self) -> list[Message]:
        """
        Build messages for LLM API call.

        Returns:
            List of messages compatible with litellm
        """
        # Start with system prompt
        messages: list[Message] = [
            {"role": "system", "content": self.config.agent.system_prompt}
        ]

        # Add conversation history - already in correct format from state
        messages.extend(self.state.get_history(50))

        return messages

    async def _handle_tool_calls(
        self, response, messages: list[Message]
    ) -> str:
        """
        Handle tool calls from the LLM response.

        Args:
            response: LLM response with tool calls
            messages: Current conversation messages

        Returns:
            Final assistant response text
        """
        # Save assistant message with tool calls
        tool_call_dicts = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in response.tool_calls
        ]
        self.state.add_message(
            {"role": "assistant", "content": response.content, "tool_calls": tool_call_dicts}
        )

        # Execute each tool call
        for tool_call in response.tool_calls:
            await self._execute_tool_call(tool_call)

        # Rebuild messages with tool responses
        messages = self._build_messages()

        # Get final response
        final_response = await self._llm_provider.chat(messages)
        self.state.add_message({"role": "assistant", "content": final_response.content})
        return final_response.content

    async def _execute_tool_call(self, tool_call: LLMToolCall) -> None:
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

        # Save tool response message
        self.state.add_message(
            {"role": "tool", "content": result, "tool_call_id": tool_call.id}
        )

    def reset(self) -> None:
        """Reset the conversation history."""
        self.state.clear_history()
