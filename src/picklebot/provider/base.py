"""Base LLM provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMToolCall:
    """A tool/function call from the LLM."""

    id: str
    name: str
    arguments: str  # JSON string


@dataclass
class LLMMessage:
    """A message in the conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[LLMToolCall]] = None


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    tool_calls: Optional[list[LLMToolCall]] = None
    model: Optional[str] = None
    usage: Optional[dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers should inherit from this class and implement
    the required methods.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize the LLM provider.

        Args:
            model: Model name/identifier
            api_key: API key for authentication
            api_base: Base URL for the API
            **kwargs: Additional provider-specific settings
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self._settings = kwargs

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send a chat request to the LLM.

        Args:
            messages: Conversation history
            tools: Optional tool/function schemas for function calling
            **kwargs: Additional request parameters

        Returns:
            LLMResponse with content and optional tool calls
        """
        pass

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        """
        Send a streaming chat request to the LLM.

        Args:
            messages: Conversation history
            tools: Optional tool/function schemas for function calling
            **kwargs: Additional request parameters

        Yields:
            Chunks of the response as they arrive
        """
        raise NotImplementedError(f"{self.provider_name} does not support streaming")

    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming."""
        return False

    def supports_tools(self) -> bool:
        """Check if this provider supports function calling."""
        return True

    @property
    def provider_name(self) -> str:
        """Return the name of this provider."""
        return self.__class__.__name__.replace("Provider", "").lower()

    def _convert_messages_to_dict(
        self, messages: list[LLMMessage]
    ) -> list[dict[str, Any]]:
        """
        Convert LLMMessage objects to dictionaries for API calls.

        Args:
            messages: List of LLMMessage objects

        Returns:
            List of message dictionaries
        """
        result = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id is not None:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls is not None:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(msg_dict)
        return result
