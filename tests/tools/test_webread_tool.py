"""Tests for webread tool."""

import pytest
from unittest.mock import AsyncMock, patch

from picklebot.tools.webread_tool import create_webread_tool
from picklebot.provider.web_read.base import ReadResult
from picklebot.core.context import SharedContext
from picklebot.utils.config import WebReadConfig
from picklebot.frontend.base import SilentFrontend


class TestCreateWebreadTool:
    """Tests for create_webread_tool factory."""

    def test_creates_tool(self, test_config):
        """Factory should create a tool."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        tool = create_webread_tool(context)

        assert tool is not None
        assert tool.name == "webread"

    def test_tool_has_correct_schema(self, test_config):
        """Tool should have correct name and parameters."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        tool = create_webread_tool(context)

        # Check tool properties
        assert tool.name == "webread"
        assert "extract content" in tool.description.lower()
        assert tool.parameters["type"] == "object"
        assert "url" in tool.parameters["properties"]
        assert tool.parameters["properties"]["url"]["type"] == "string"
        assert tool.parameters["required"] == ["url"]


class TestWebreadToolExecution:
    """Tests for webread tool execution."""

    @pytest.mark.asyncio
    async def test_returns_markdown_content(self, test_config):
        """Tool should return markdown content."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        mock_result = ReadResult(
            url="https://example.com",
            title="Example Page",
            content="# Example\n\nThis is content.",
        )

        with patch(
            "picklebot.provider.web_read.WebReadProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.read = AsyncMock(return_value=mock_result)
            mock_from_config.return_value = mock_provider

            tool = create_webread_tool(context)
            frontend = SilentFrontend()
            result = await tool.execute(frontend=frontend, url="https://example.com")

        assert "Example Page" in result
        assert "# Example" in result
        assert "This is content." in result

    @pytest.mark.asyncio
    async def test_returns_error_message(self, test_config):
        """Tool should return error message on failure."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        mock_result = ReadResult(
            url="https://example.com",
            title="",
            content="",
            error="Failed to load page",
        )

        with patch(
            "picklebot.provider.web_read.WebReadProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.read = AsyncMock(return_value=mock_result)
            mock_from_config.return_value = mock_provider

            tool = create_webread_tool(context)
            frontend = SilentFrontend()
            result = await tool.execute(frontend=frontend, url="https://example.com")

        assert "Error reading" in result
        assert "Failed to load page" in result
