"""Webread tool factory."""

from typing import TYPE_CHECKING

from picklebot.tools.base import BaseTool, tool
from picklebot.provider.web_read import WebReadProvider

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession
    from picklebot.core.context import SharedContext


def create_webread_tool(context: "SharedContext") -> BaseTool | None:
    """Factory to create webread tool with injected context.

    Args:
        context: SharedContext for accessing config

    Returns:
        Tool function for web page reading
    """
    if not context.config.webread:
        return None

    provider = WebReadProvider.from_config(context.config)

    @tool(
        name="webread",
        description=(
            "Read and extract content from a web page. "
            "Returns the page content as markdown."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to read",
                }
            },
            "required": ["url"],
        },
    )
    async def webread(url: str, session: "AgentSession") -> str:
        """Read a web page and return markdown content.

        Args:
            url: The URL to read
            session: The agent session context

        Returns:
            Markdown content of the page or error message
        """

        result = await provider.read(url)

        if result.error:
            return f"Error reading {url}: {result.error}"

        return f"**{result.title}**\n\n{result.content}"

    return webread
