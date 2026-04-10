"""Searxng Search API provider."""

from typing import TYPE_CHECKING
import httpx

from .base import WebSearchProvider, SearchResult

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class SearxngSearchProvider(WebSearchProvider):
    """Web search provider using Searxng Search API."""

    def __init__(self, config: "Config"):
        """Initialize Searxng Search provider.

        Args:
            api_key: No need
            api_base: searxng server url
        """
        self.api_key = config.websearch.api_key
        self.api_base = config.websearch.api_base

    async def search(self, query: str) -> list[SearchResult]:
        """Search the web using Searxng Search API.

        Args:
            query: Search query string

        Returns:
            List of normalized search results

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.api_base,
                headers={
                    "Accept": "application/json",
                },
                params={
                    "q": query,
                    "format": "json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
            )

        return results
