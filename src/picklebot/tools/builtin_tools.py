"""Built-in tools for pickle-bot."""

import platform
from datetime import datetime

from picklebot.tools.base import BaseTool
from picklebot.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    """Simple echo tool for testing."""

    name = "echo"
    description = "Echo back the input text"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to echo back",
            },
        },
        "required": ["text"],
    }

    async def execute(self, text: str) -> str:
        return f"Echo: {text}"


class TimeTool(BaseTool):
    """Get current time and date."""

    name = "get_time"
    description = "Get the current time and date"
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Optional timezone (e.g., 'UTC', 'America/New_York')",
            },
        },
        "required": [],
    }

    async def execute(self, timezone: str | None = None) -> str:
        return f"Current local time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


class SystemTool(BaseTool):
    """Get system information."""

    name = "get_system_info"
    description = "Get information about the system"
    parameters = {
        "type": "object",
        "properties": {
            "info_type": {
                "type": "string",
                "enum": ["all", "platform", "python", "machine"],
                "description": "Type of system information to retrieve",
            },
        },
        "required": [],
    }

    async def execute(self, info_type: str = "all") -> str:
        info = []

        if info_type in ["all", "platform"]:
            info.append(f"Platform: {platform.platform()}")
            info.append(f"OS: {platform.system()} {platform.release()}")
            info.append(f"Architecture: {platform.machine()}")

        if info_type in ["all", "python"]:
            import sys
            info.append(f"Python: {sys.version}")

        if info_type in ["all", "machine"]:
            import socket
            info.append(f"Hostname: {socket.gethostname()}")

        return "\n".join(info) if info else "No information available"


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in tools with the given registry."""
    registry.register(EchoTool())
    registry.register(TimeTool())
    registry.register(SystemTool())
