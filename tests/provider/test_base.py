"""Tests for LLMProvider base class."""

from picklebot.provider.base import LLMProvider

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
