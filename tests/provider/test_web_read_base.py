"""Tests for WebReadProvider base class."""

import pytest

from picklebot.provider.web_read.base import ReadResult, WebReadProvider
from picklebot.utils.config import Config, WebReadConfig


class TestReadResult:
    """Tests for ReadResult model."""

    def test_read_result_creation(self):
        """ReadResult should create with all fields."""
        result = ReadResult(
            url="https://example.com",
            title="Example",
            content="# Content\n\nSome text",
        )
        assert result.url == "https://example.com"
        assert result.title == "Example"
        assert result.content == "# Content\n\nSome text"
        assert result.error is None

    def test_read_result_with_error(self):
        """ReadResult should accept error field."""
        result = ReadResult(
            url="https://example.com",
            title="",
            content="",
            error="Failed to fetch",
        )
        assert result.error == "Failed to fetch"


class TestWebReadProvider:
    """Tests for WebReadProvider abstract class."""

    def test_cannot_instantiate_abstract(self):
        """WebReadProvider should not be instantiable directly."""
        with pytest.raises(TypeError):
            WebReadProvider()

    def test_from_config_raises_for_unknown_provider(self, test_config: Config):
        """from_config should raise ValueError for unknown provider."""
        test_config.webread = WebReadConfig(provider="unknown")
        with pytest.raises(ValueError, match="Unknown webread provider"):
            WebReadProvider.from_config(test_config)

    def test_from_config_raises_when_not_configured(self, test_config: Config):
        """from_config should raise ValueError when webread not configured."""
        test_config.webread = None
        with pytest.raises(ValueError, match="Webread not configured"):
            WebReadProvider.from_config(test_config)
