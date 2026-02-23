"""Tests for Crawl4AIProvider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from picklebot.provider.web_read.crawl4ai import Crawl4AIProvider
from picklebot.provider.web_read.base import ReadResult, WebReadProvider
from picklebot.utils.config import Config, Crawl4AIWebReadConfig


class TestCrawl4AIProvider:
    """Tests for Crawl4AIProvider."""

    def test_init(self):
        """Crawl4AIProvider should initialize without args."""
        provider = Crawl4AIProvider()
        assert provider is not None

    def test_from_config(self, test_config: Config):
        """from_config should create provider from config."""
        test_config.webread = Crawl4AIWebReadConfig()
        provider = WebReadProvider.from_config(test_config)
        assert isinstance(provider, Crawl4AIProvider)

    @pytest.mark.asyncio
    async def test_read_returns_markdown(self):
        """read should return ReadResult with markdown content."""
        provider = Crawl4AIProvider()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.markdown = "# Example Page\n\nThis is content."
        mock_result.metadata = {"title": "Example Page"}
        mock_result.error_message = None

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "picklebot.provider.web_read.crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler,
        ):
            result = await provider.read("https://example.com")

        assert isinstance(result, ReadResult)
        assert result.url == "https://example.com"
        assert result.title == "Example Page"
        assert result.content == "# Example Page\n\nThis is content."
        assert result.error is None

    @pytest.mark.asyncio
    async def test_read_handles_failure(self):
        """read should return error on failure."""
        provider = Crawl4AIProvider()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "Failed to load page"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "picklebot.provider.web_read.crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler,
        ):
            result = await provider.read("https://example.com")

        assert result.error == "Failed to load page"
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_read_handles_exception(self):
        """read should catch and return exceptions."""
        provider = Crawl4AIProvider()

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=Exception("Network error"))
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "picklebot.provider.web_read.crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler,
        ):
            result = await provider.read("https://example.com")

        assert "Network error" in result.error
