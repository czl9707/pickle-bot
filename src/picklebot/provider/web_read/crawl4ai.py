"""Crawl4AI provider for web page reading."""

from typing import TYPE_CHECKING
from crawl4ai import AsyncWebCrawler

from .base import WebReadProvider, ReadResult

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class Crawl4AIProvider(WebReadProvider):
    """Web read provider using Crawl4AI."""

    def __init__(self):
        """Initialize Crawl4AI provider."""
        pass

    @staticmethod
    def from_config(config: "Config") -> "Crawl4AIProvider":
        """Create provider from config.

        Args:
            config: Application config

        Returns:
            Crawl4AIProvider instance
        """
        return Crawl4AIProvider()

    async def read(self, url: str) -> ReadResult:
        """Read a web page using Crawl4AI.

        Args:
            url: URL to read

        Returns:
            ReadResult with markdown content or error
        """
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(url=url)

                if not result.success:
                    return ReadResult(
                        url=url,
                        title="",
                        content="",
                        error=result.error_message or "Failed to crawl page",
                    )

                return ReadResult(
                    url=url,
                    title=(
                        result.metadata.get("title", "")
                        if result.metadata
                        else ""
                    ),
                    content=result.markdown or "",
                    error=None,
                )
        except Exception as e:
            return ReadResult(
                url=url,
                title="",
                content="",
                error=str(e),
            )
