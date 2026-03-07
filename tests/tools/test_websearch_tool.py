"""Tests for websearch tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from picklebot.tools.websearch_tool import create_websearch_tool
from picklebot.provider.web_search.base import SearchResult
from picklebot.core.context import SharedContext
from picklebot.utils.config import BraveWebSearchConfig


def _make_mock_session():
    """Helper to create a mock session."""
    mock_session = MagicMock()
    mock_session.session_id = "test-session"
    mock_session.agent_id = "test-agent"
    return mock_session


class TestCreateWebsearchTool:
    """Tests for create_websearch_tool factory."""

    def test_creates_tool_with_correct_schema(self, test_config):
        """Factory should create a tool with correct name, description, and parameters."""
        test_config.websearch = BraveWebSearchConfig(api_key="test-key")
        context = SharedContext(config=test_config)

        tool = create_websearch_tool(context)

        assert tool is not None
        assert tool.name == "websearch"
        assert "search the web" in tool.description.lower()
        assert tool.parameters["type"] == "object"
        assert "query" in tool.parameters["properties"]
        assert tool.parameters["properties"]["query"]["type"] == "string"
        assert tool.parameters["required"] == ["query"]


class TestWebsearchToolExecution:
    """Tests for websearch tool execution."""

    async def test_returns_formatted_results(self, test_config):
        """Tool should return formatted markdown results."""
        test_config.websearch = BraveWebSearchConfig(api_key="test-key")
        context = SharedContext(config=test_config)

        mock_results = [
            SearchResult(
                title="Example",
                url="https://example.com",
                snippet="A description",
            ),
            SearchResult(
                title="Another",
                url="https://another.com",
                snippet="Another description",
            ),
        ]

        with patch(
            "picklebot.provider.web_search.WebSearchProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.search = AsyncMock(return_value=mock_results)
            mock_from_config.return_value = mock_provider

            tool = create_websearch_tool(context)
            mock_session = _make_mock_session()
            result = await tool.execute(session=mock_session, query="test query")

        assert "Example" in result
        assert "https://example.com" in result
        assert "Another" in result
        assert "https://another.com" in result

    async def test_returns_no_results_message(self, test_config):
        """Tool should return message when no results found."""
        test_config.websearch = BraveWebSearchConfig(api_key="test-key")
        context = SharedContext(config=test_config)

        with patch(
            "picklebot.provider.web_search.WebSearchProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.search = AsyncMock(return_value=[])
            mock_from_config.return_value = mock_provider

            tool = create_websearch_tool(context)
            mock_session = _make_mock_session()
            result = await tool.execute(session=mock_session, query="test query")

        assert result == "No results found."
