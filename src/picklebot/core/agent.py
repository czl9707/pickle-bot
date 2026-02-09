"""Agent core with LiteLLM integration."""

import asyncio
from typing import Any, Optional

from litellm import acompletion

from picklebot.core.config import AgentConfig
from picklebot.core.state import AgentState, Message


class Agent:
    """
    Main Agent class that handles chat with LiteLLM integration.

    Supports function calling through the skills system.
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize the agent.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.state = AgentState()
        self._skill_registry = None  # Will be set by the CLI or explicitly

    def set_skill_registry(self, registry) -> None:
        """Set the skill registry for function calling."""
        self._skill_registry = registry

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """
        Get tool schemas from the skill registry for LiteLLM.

        Returns:
            List of tool/function schemas
        """
        if self._skill_registry is None:
            return []

        return self._skill_registry.get_tool_schemas()

    def _build_litellm_kwargs(self) -> dict[str, Any]:
        """Build kwargs for LiteLLM API calls."""
        return {
            "model": f"openai/{self.config.llm.model}",  # Z.ai is OpenAI-compatible
            "api_base": self.config.llm.api_base,
            "api_key": self.config.llm.api_key,
        }

    async def chat(self, message: str, stream: bool = False) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User message
            stream: Whether to stream the response (not implemented yet)

        Returns:
            Assistant's response text
        """
        # Add user message to history
        self.state.add_message("user", message)

        # Get conversation history
        messages = self._get_messages_with_system()

        # Prepare LiteLLM call
        kwargs = self._build_litellm_kwargs()
        kwargs["messages"] = messages

        # Add tools if skill registry is available
        tool_schemas = self.get_tool_schemas()
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        # Make API call
        response = await acompletion(**kwargs)

        # Handle response
        return await self._handle_response(response)

    def _get_messages_with_system(self) -> list[dict[str, Any]]:
        """Get messages with system prompt prepended."""
        messages = [{"role": "system", "content": self.config.agent.system_prompt}]
        messages.extend(self.state.get_history(self.config.agent.max_history))
        return messages

    async def _handle_response(self, response: dict[str, Any]) -> str:
        """
        Handle the response from LiteLLM.

        Supports function calling through tool_calls.

        Args:
            response: Raw response from LiteLLM

        Returns:
            Final assistant response text
        """
        choice = response["choices"][0]
        message = choice["message"]

        # Check for tool calls (function calling)
        tool_calls = message.get("tool_calls")
        if tool_calls:
            # Save assistant message with tool calls
            self.state.add_message(
                "assistant",
                message.get("content", ""),
                tool_calls=tool_calls,
            )

            # Execute each tool call
            for tool_call in tool_calls:
                await self._execute_tool_call(tool_call)

            # Get final response after tool execution
            return await self._get_final_response()

        # No tool calls, return the content directly
        content = message.get("content", "")
        self.state.add_message("assistant", content)
        return content

    async def _execute_tool_call(self, tool_call: dict[str, Any]) -> None:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call dict from LiteLLM response
        """
        if self._skill_registry is None:
            result = "Error: No skill registry available"
        else:
            function = tool_call["function"]
            name = function["name"]
            arguments = function.get("arguments", "{}")

            import json

            try:
                args = json.loads(arguments) if isinstance(arguments, str) else arguments
                result = await self._skill_registry.execute_tool(name, **args)
            except Exception as e:
                result = f"Error executing skill: {e}"

        # Save tool response message
        self.state.add_message(
            "tool",
            result,
            tool_call_id=tool_call["id"],
        )

    async def _get_final_response(self) -> str:
        """Get the final response after tool execution."""
        messages = self._get_messages_with_system()
        kwargs = self._build_litellm_kwargs()
        kwargs["messages"] = messages

        response = await acompletion(**kwargs)
        content = response["choices"][0]["message"].get("content", "")
        self.state.add_message("assistant", content)
        return content

    def reset(self) -> None:
        """Reset the conversation history."""
        self.state.clear_history()
