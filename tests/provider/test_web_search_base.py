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

    def test_from_config_raises_when_not_configured(self, test_config: Config):
        """from_config should raise ValueError when websearch not configured."""
        test_config.websearch = None
        with pytest.raises(ValueError, match="Websearch not configured"):
            WebSearchProvider.from_config(test_config)
