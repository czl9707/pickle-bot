"""Tests for LLMProvider base class."""

from picklebot.provider.base import LLMProvider
from picklebot.provider.providers import (
    AnthropicProvider,
    OpenAIProvider,
    OtherProvider,
    ZaiProvider,
)


class TestProviderMetadata:
    """Test provider metadata properties."""

    def test_openai_has_required_metadata(self):
        assert OpenAIProvider.display_name == "OpenAI"
        assert OpenAIProvider.default_model == "gpt-4o"
        assert OpenAIProvider.env_var == "OPENAI_API_KEY"

    def test_anthropic_has_required_metadata(self):
        assert AnthropicProvider.display_name == "Anthropic Claude"
        assert AnthropicProvider.default_model == "claude-3-5-sonnet-latest"
        assert AnthropicProvider.env_var == "ANTHROPIC_API_KEY"

    def test_zai_has_required_metadata(self):
        assert ZaiProvider.display_name == "Z.ai"
        assert ZaiProvider.default_model == "zai-1.0"
        assert ZaiProvider.env_var == "ZAI_API_KEY"

    def test_other_has_required_metadata(self):
        assert OtherProvider.display_name == "Other (custom)"
        assert OtherProvider.default_model == ""

    def test_env_var_is_optional(self):
        # OtherProvider has no env_var
        assert OtherProvider.env_var is None

    def test_api_base_is_optional(self):
        # None of our providers define api_base by default
        assert OpenAIProvider.api_base is None


class TestGetOnboardingProviders:
    """Test get_onboarding_providers classmethod."""

    def test_returns_list_of_tuples(self):
        providers = LLMProvider.get_onboarding_providers()
        assert isinstance(providers, list)
        assert all(isinstance(p, tuple) and len(p) == 2 for p in providers)

    def test_excludes_other_provider(self):
        providers = LLMProvider.get_onboarding_providers()
        config_names = [name for name, _ in providers]
        assert "other" not in config_names

    def test_includes_main_providers(self):
        providers = LLMProvider.get_onboarding_providers()
        config_names = [name for name, _ in providers]
        assert "openai" in config_names
        assert "anthropic" in config_names
        assert "zai" in config_names

    def test_returns_provider_classes(self):
        providers = LLMProvider.get_onboarding_providers()
        for config_name, provider_cls in providers:
            assert issubclass(provider_cls, LLMProvider)
            assert provider_cls.display_name  # has metadata
