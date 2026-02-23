"""Websearch tool factory."""

from typing import TYPE_CHECKING

from picklebot.tools.base import BaseTool, tool
from picklebot.provider.web_search import WebSearchProvider

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext
    from picklebot.frontend import Frontend


def create_websearch_tool(context: "SharedContext") -> BaseTool | None:
    """Factory to create websearch tool with injected context.

    Args:
        context: SharedContext for accessing config

    Returns:
        Tool function for web search
    """
    if not context.config.websearch:
        return None

    provider = WebSearchProvider.from_config(context.config)

    @tool(
        name="websearch",
        description=(
            "Search the web for information. "
            "Returns a list of results with titles, URLs, and snippets."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    )
    async def websearch(frontend: "Frontend", query: str) -> str:
        """Search the web and return formatted results.

        Args:
            frontend: Frontend for displaying output (unused)
            query: The search query string

        Returns:
            Formatted markdown string with search results
        """

        results = await provider.search(query)

        if not results:
            return "No results found."

        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. **{r.title}**\n   {r.url}\n   {r.snippet}")
        return "\n\n".join(output)

    return websearch
