"""Agent core with LLM provider abstraction."""

import json
from typing import Any

from picklebot.core.config import Config
from picklebot.core.state import AgentState, Message
from picklebot.llm import LLMMessage, LLMToolCall, create_provider


class Agent:
    """
    Main Agent class that handles chat with pluggable LLM providers.

    Supports function calling through the skills system.
    """

    def __init__(self, config: Config):
        """
        Initialize the agent.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.state = AgentState()
        self._skill_registry = None  # Will be set by the CLI or explicitly
        self._llm_provider = create_provider(config.llm)

    def set_skill_registry(self, registry) -> None:
        """Set the skill registry for function calling."""
        self._skill_registry = registry

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """
        Get tool schemas from the skill registry.

        Returns:
            List of tool/function schemas
        """
        if self._skill_registry is None:
            return []

        return self._skill_registry.get_tool_schemas()

    async def chat(self, message: str, stream: bool = False) -> str:
        """
        Send a message to the LLM and get a response.

        Args:
            message: User message
            stream: Whether to stream the response

        Returns:
            Assistant's response text
        """
        # Add user message to history
        self.state.add_message("user", message)

        # Build messages for LLM
        messages = self._build_messages()

        # Get tool schemas
        tools = self.get_tool_schemas() if self._skill_registry else None

        # Call LLM provider
        response = await self._llm_provider.chat(messages, tools)

        # Handle tool calls
        if response.tool_calls:
            return await self._handle_tool_calls(response, messages)

        # No tool calls, save and return content
        self.state.add_message("assistant", response.content)
        return response.content

    async def chat_stream(self, message: str):
        """
        Send a message to the LLM and stream the response.

        Args:
            message: User message

        Yields:
            Chunks of the response as they arrive
        """
        # Add user message to history
        self.state.add_message("user", message)

        # Build messages for LLM
        messages = self._build_messages()

        # Get tool schemas
        tools = self.get_tool_schemas() if self._skill_registry else None

        # Stream from LLM provider
        full_response = ""
        async for chunk in self._llm_provider.chat_stream(messages, tools):
            full_response += chunk
            yield chunk

        # Save complete response
        self.state.add_message("assistant", full_response)

    def _build_messages(self) -> list[LLMMessage]:
        """
        Build messages for LLM API call.

        Returns:
            List of LLMMessage objects
        """
        # Start with system prompt
        messages = [
            LLMMessage(role="system", content=self.config.agent.system_prompt)
        ]

        # Add conversation history
        for msg in self.state.get_history(50):
            # Convert tool_calls to LLMToolCall objects if present
            tool_calls = None
            if msg.get("tool_calls"):
                tool_calls = [
                    LLMToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    )
                    for tc in msg["tool_calls"]
                ]

            messages.append(
                LLMMessage(
                    role=msg["role"],
                    content=msg["content"],
                    tool_call_id=msg.get("tool_call_id"),
                    tool_calls=tool_calls,
                )
            )

        return messages

    async def _handle_tool_calls(
        self, response, messages: list[LLMMessage]
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
        self.state.add_message("assistant", response.content, tool_calls=tool_call_dicts)

        # Execute each tool call
        for tool_call in response.tool_calls:
            await self._execute_tool_call(tool_call)

        # Rebuild messages with tool responses
        messages = self._build_messages()

        # Get final response
        final_response = await self._llm_provider.chat(messages)
        self.state.add_message("assistant", final_response.content)
        return final_response.content

    async def _execute_tool_call(self, tool_call: LLMToolCall) -> None:
        """
        Execute a single tool call.

        Args:
            tool_call: Tool call from LLM response
        """
        if self._skill_registry is None:
            result = "Error: No skill registry available"
        else:
            try:
                args = json.loads(tool_call.arguments)
                result = await self._skill_registry.execute_tool(
                    tool_call.name, **args
                )
            except Exception as e:
                result = f"Error executing skill: {e}"

        # Save tool response message
        self.state.add_message("tool", result, tool_call_id=tool_call.id)

    def reset(self) -> None:
        """Reset the conversation history."""
        self.state.clear_history()
