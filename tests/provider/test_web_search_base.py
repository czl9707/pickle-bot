"""Tests for WebSearchProvider base class."""

import pytest

from picklebot.provider.web_search.base import SearchResult, WebSearchProvider
from picklebot.utils.config import Config


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_search_result_creation(self):
        """SearchResult should create with all fields."""
        result = SearchResult(
            title="Example",
            url="https://example.com",
            snippet="A description",
        )
        assert result.title == "Example"
        assert result.url == "https://example.com"
        assert result.snippet == "A description"


class TestWebSearchProvider:
    """Tests for WebSearchProvider abstract class."""

    def test_cannot_instantiate_abstract(self):
        """WebSearchProvider should not be instantiable directly."""
        with pytest.raises(TypeError):
            WebSearchProvider()

    def test_from_config_raises_for_unknown_provider(self, test_config: Config):
        """from_config should raise ValueError for unknown provider."""
        # Create a mock websearch config with unknown provider
        from picklebot.utils.config import WebSearchConfig

        test_config.websearch = WebSearchConfig(provider="unknown", api_key="test-key")
        with pytest.raises(ValueError, match="Unknown websearch provider"):
            WebSearchProvider.from_config(test_config)

    def test_from_config_raises_when_not_configured(self, test_config: Config):
        """from_config should raise ValueError when websearch not configured."""
        test_config.websearch = None
        with pytest.raises(ValueError, match="Websearch not configured"):
            WebSearchProvider.from_config(test_config)
