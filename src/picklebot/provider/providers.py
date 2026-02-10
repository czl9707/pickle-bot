"""Concrete LLM provider implementations."""

from typing import Any

from litellm import acompletion

from picklebot.provider.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMToolCall


class ZaiProvider(BaseLLMProvider):
    """
    Z.ai LLM provider.

    Uses the OpenAI-compatible API via LiteLLM.
    """

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat request to Z.ai."""
        # Convert messages to LiteLLM format
        lite_messages = self._convert_messages_to_dict(messages)

        # Build request kwargs
        request_kwargs = {
            "model": self.model,
            "messages": lite_messages,
        }

        if self.api_base:
            request_kwargs["api_base"] = self.api_base

        if tools:
            request_kwargs["tools"] = tools

        request_kwargs.update(kwargs)

        # Make the API call
        response = await acompletion(**request_kwargs)

        # Parse response
        choice = response["choices"][0]
        message = choice["message"]

        content = message.get("content", "")
        tool_calls = None

        if message.get("tool_calls"):
            tool_calls = [
                LLMToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in message["tool_calls"]
            ]

        return LLMResponse(
            content=content or "",
            tool_calls=tool_calls,
            model=response.get("model"),
            usage=response.get("usage"),
        )

    def supports_streaming(self) -> bool:
        """Z.ai doesn't support streaming yet."""
        return False


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM provider.

    Uses LiteLLM for OpenAI API access.
    """

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat request to OpenAI."""
        lite_messages = self._convert_messages_to_dict(messages)

        request_kwargs = {
            "model": self.model,
            "messages": lite_messages,
        }

        if tools:
            request_kwargs["tools"] = tools

        request_kwargs.update(kwargs)

        response = await acompletion(**request_kwargs)

        choice = response["choices"][0]
        message = choice["message"]

        content = message.get("content", "")
        tool_calls = None

        if message.get("tool_calls"):
            tool_calls = [
                LLMToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in message["tool_calls"]
            ]

        return LLMResponse(
            content=content or "",
            tool_calls=tool_calls,
            model=response.get("model"),
            usage=response.get("usage"),
        )


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM provider.

    Uses LiteLLM for Anthropic API access.
    """

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat request to Anthropic."""
        lite_messages = self._convert_messages_to_dict(messages)

        request_kwargs = {
            "model": self.model,
            "messages": lite_messages,
        }

        if tools:
            request_kwargs["tools"] = tools

        request_kwargs.update(kwargs)

        response = await acompletion(**request_kwargs)

        choice = response["choices"][0]
        message = choice["message"]

        content = message.get("content", "")
        tool_calls = None

        if message.get("tool_calls"):
            tool_calls = [
                LLMToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in message["tool_calls"]
            ]

        return LLMResponse(
            content=content or "",
            tool_calls=tool_calls,
            model=response.get("model"),
            usage=response.get("usage"),
        )
