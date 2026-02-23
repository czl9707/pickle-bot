"""Brave Search API provider."""

from typing import TYPE_CHECKING
import httpx

from .base import WebSearchProvider, SearchResult

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class BraveSearchProvider(WebSearchProvider):
    """Web search provider using Brave Search API."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        """Initialize Brave Search provider.

        Args:
            api_key: Brave Search API key
        """
        self.api_key = api_key

    @staticmethod
    def from_config(config: "Config") -> "BraveSearchProvider":
        """Create provider from config.

        Args:
            config: Application config

        Returns:
            Configured BraveSearchProvider
        """
        return BraveSearchProvider(api_key=config.websearch.api_key)

    async def search(self, query: str) -> list[SearchResult]:
        """Search the web using Brave Search API.

        Args:
            query: Search query string

        Returns:
            List of normalized search results

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.BASE_URL,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
                params={
                    "q": query,
                    "count": 10,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                )
            )

        return results
