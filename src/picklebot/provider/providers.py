"""Concrete LLM provider implementations."""

from picklebot.provider.base import LLMProvider


class ZaiProvider(LLMProvider):
    """Z.ai LLM provider (OpenAI-compatible API)."""
    provider_config_name = ["zai", "z_ai"]


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""
    provider_config_name = ["openai"]


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""
    provider_config_name = ["anthropic", "claude"]
