"""Crawl4AI provider for web page reading."""

from crawl4ai import AsyncWebCrawler

from .base import WebReadProvider, ReadResult


class Crawl4AIProvider(WebReadProvider):
    """Web read provider using Crawl4AI."""

    def __init__(self):
        """Initialize Crawl4AI provider."""
        pass

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
                    raise Exception(result.error_message or "Failed to crawl page")

                return ReadResult(
                    url=url,
                    title=(result.metadata.get("title", "") if result.metadata else ""),
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
