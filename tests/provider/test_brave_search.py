"""Tests for BraveSearchProvider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from picklebot.provider.web_search.brave import BraveSearchProvider
from picklebot.provider.web_search.base import SearchResult
from picklebot.utils.config import Config, WebSearchConfig


class TestBraveSearchProvider:
    """Tests for BraveSearchProvider."""

    def test_init(self):
        """BraveSearchProvider should store api_key."""
        provider = BraveSearchProvider(api_key="test-key")
        assert provider.api_key == "test-key"

    def test_from_config(self, test_config: Config):
        """from_config should create provider from config."""
        test_config.websearch = WebSearchConfig(provider="brave", api_key="test-key")
        provider = BraveSearchProvider.from_config(test_config)
        assert isinstance(provider, BraveSearchProvider)
        assert provider.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_search_returns_normalized_results(self):
        """search should return list of SearchResult."""
        provider = BraveSearchProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Example Title",
                        "url": "https://example.com",
                        "description": "Example description",
                    },
                    {
                        "title": "Another Title",
                        "url": "https://another.com",
                        "description": "Another description",
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            results = await provider.search("test query")

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Example Title"
        assert results[0].url == "https://example.com"
        assert results[0].snippet == "Example description"

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self):
        """search should return empty list when no results."""
        provider = BraveSearchProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            results = await provider.search("test query")

        assert results == []
