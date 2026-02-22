"""Concrete LLM provider implementations."""

from picklebot.provider.base import LLMProvider


class ZaiProvider(LLMProvider):
    """Z.ai LLM provider (OpenAI-compatible API)."""

    provider_config_name = ["zai", "z_ai"]
    display_name = "Z.ai"
    default_model = "zai-1.0"
    env_var = "ZAI_API_KEY"


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    provider_config_name = ["openai"]
    display_name = "OpenAI"
    default_model = "gpt-4o"
    env_var = "OPENAI_API_KEY"


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    provider_config_name = ["anthropic", "claude"]
    display_name = "Anthropic Claude"
    default_model = "claude-3-5-sonnet-latest"
    env_var = "ANTHROPIC_API_KEY"


class OtherProvider(LLMProvider):
    """Fallback for custom/self-hosted providers."""

    provider_config_name = ["other"]
    display_name = "Other (custom)"
    default_model = ""
