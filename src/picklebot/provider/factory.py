"""LLM provider factory."""

from picklebot.config import LLMConfig
from picklebot.llm.base import BaseLLMProvider
from picklebot.llm.providers import AnthropicProvider, OpenAIProvider, ZaiProvider


# Registry of available providers
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "zai": ZaiProvider,
    "z_ai": ZaiProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
}


def register_provider(name: str, provider_class: type[BaseLLMProvider]) -> None:
    """
    Register a new LLM provider.

    Args:
        name: Provider name (as used in config)
        provider_class: Provider class to register
    """
    _PROVIDERS[name.lower()] = provider_class


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    """
    Create an LLM provider instance from configuration.

    Args:
        config: LLM configuration

    Returns:
        Initialized LLM provider instance

    Raises:
        ValueError: If provider name is unknown
    """
    provider_name = config.provider.lower()

    if provider_name not in _PROVIDERS:
        known = ", ".join(_PROVIDERS.keys())
        raise ValueError(
            f"Unknown LLM provider: {config.provider}. "
            f"Known providers: {known}"
        )

    provider_class = _PROVIDERS[provider_name]

    return provider_class(
        model=config.model,
        api_key=config.api_key,
        api_base=config.api_base,
    )


def get_available_providers() -> list[str]:
    """Get list of available provider names."""
    return list(_PROVIDERS.keys())
