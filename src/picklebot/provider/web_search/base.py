"""Base class for web search providers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class SearchResult(BaseModel):
    """Normalized search result from any provider."""

    title: str
    url: str
    snippet: str


class WebSearchProvider(ABC):
    """Abstract base class for web search providers."""

    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        """Search the web and return normalized results.

        Args:
            query: The search query string

        Returns:
            List of normalized SearchResult objects
        """
        pass

    @staticmethod
    def from_config(config: "Config") -> "WebSearchProvider":
        """Factory method to create provider from config.

        Args:
            config: Application config with websearch settings

        Returns:
            Configured WebSearchProvider instance

        Raises:
            ValueError: If provider is unknown or not configured
        """
        if config.websearch is None:
            raise ValueError("Websearch not configured")

        match config.websearch.provider:
            case "brave":
                from .brave import BraveSearchProvider

                return BraveSearchProvider(config)
            case _:
                raise ValueError(
                    f"Unknown websearch provider: {config.websearch.provider}"
                )
