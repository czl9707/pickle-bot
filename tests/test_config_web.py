"""Tests for websearch and webread config models."""

import pytest
from pydantic import ValidationError

from picklebot.utils.config import WebSearchConfig, WebReadConfig


class TestWebSearchConfig:
    """Tests for WebSearchConfig model."""

    def test_websearch_config_with_api_key(self):
        """WebSearchConfig should accept api_key."""
        config = WebSearchConfig(provider="brave", api_key="test-key")
        assert config.provider == "brave"
        assert config.api_key == "test-key"

    def test_websearch_config_requires_api_key(self):
        """WebSearchConfig should require api_key."""
        with pytest.raises(ValidationError):
            WebSearchConfig(provider="brave")

    def test_websearch_config_default_provider(self):
        """WebSearchConfig should default provider to brave."""
        config = WebSearchConfig(api_key="test-key")
        assert config.provider == "brave"


class TestWebReadConfig:
    """Tests for WebReadConfig model."""

    def test_webread_config_defaults(self):
        """WebReadConfig should default provider to crawl4ai."""
        config = WebReadConfig()
        assert config.provider == "crawl4ai"


class TestConfigWithWeb:
    """Tests for Config with websearch/webread fields."""

    def test_config_with_websearch(self, test_config):
        """Config should accept websearch field."""
        assert test_config.websearch is None

    def test_config_with_webread(self, test_config):
        """Config should accept webread field."""
        assert test_config.webread is None
