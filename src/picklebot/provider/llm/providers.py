"""Concrete LLM provider implementations."""

from .base import LLMProvider


class ZaiProvider(LLMProvider):
    """Z.ai LLM provider (OpenAI-compatible API)."""

    provider_config_name = ["zai", "z_ai"]
    display_name = "Z.ai"
    default_model = "zai/glm-5"


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    provider_config_name = ["openai"]
    display_name = "OpenAI"
    default_model = "gpt-5"


class OtherProvider(LLMProvider):
    """Fallback for custom/self-hosted providers."""

    provider_config_name = ["other"]
    display_name = "Other (custom)"
