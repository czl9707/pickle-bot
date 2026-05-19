"""Base LLM provider abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, cast, TYPE_CHECKING

from litellm import acompletion, Choices
from litellm.types.completion import ChatCompletionMessageParam as Message
from litellm.types.utils import OpenAIChatCompletionFinishReason

if TYPE_CHECKING:
    from picklebot.utils.config import LLMConfig

StopReason = OpenAIChatCompletionFinishReason


@dataclass
class LLMToolCall:
    """
    A tool/function call from the LLM.

    Simplified adapter over litellm's ChatCompletionMessageToolCall
    which has nested structure (function.name, function.arguments).
    """

    id: str
    name: str
    arguments: str  # JSON string


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers inherit from this and get the default `chat` implementation
    via litellm. Subclasses only need to define `provider_config_name`.
    """

    provider_config_name: list[str]
    name2provider: dict[str, type["LLMProvider"]] = {}

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Friendly name for onboarding wizard."""
        ...

    default_model: str | None = None
    env_var: str | None = None
    api_base: str | None = None

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature
        self.max_tokens = max_tokens

    def __init_subclass__(cls):
        for c_name in cls.provider_config_name:
            LLMProvider.name2provider[c_name] = cls
        return super().__init_subclass__()

    @classmethod
    def get_onboarding_providers(cls) -> list[tuple[str, type["LLMProvider"]]]:
        """Return list of (config_name, provider_class) for onboarding wizard.

        Returns unique providers (first config_name only), excluding "other".
        "other" is handled separately as fallback.
        """
        seen = set()
        providers = []
        for config_name, provider_cls in cls.name2provider.items():
            if config_name == "other":
                continue
            if provider_cls not in seen:
                seen.add(provider_cls)
                providers.append((config_name, provider_cls))
        return providers

    @staticmethod
    def from_config(config: "LLMConfig") -> "LLMProvider":
        """Create a provider from config."""
        provider_name = config.provider.lower()
        if provider_name not in LLMProvider.name2provider:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = LLMProvider.name2provider[provider_name]
        return provider_class(
            model=config.model,
            api_key=config.api_key,
            api_base=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> tuple[str, list[LLMToolCall], StopReason]:
        """
        Send a chat request to the LLM.

        Default implementation using litellm. Subclasses can override
        if provider-specific behavior is needed.

        Returns:
            Tuple of (content, tool_calls, stop_reason)
        """
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if self.api_base:
            request_kwargs["api_base"] = self.api_base
        if tools:
            request_kwargs["tools"] = tools
        request_kwargs.update(kwargs)

        response = await acompletion(**request_kwargs)

        choice = cast(Choices, response.choices[0])
        message = choice.message
        stop_reason = choice.finish_reason

        return (
            message.content or "",
            [
                LLMToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in (message.tool_calls or [])
            ],
            stop_reason,
        )
