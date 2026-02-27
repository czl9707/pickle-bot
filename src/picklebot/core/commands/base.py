"""Base classes for slash commands."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class Command(ABC):
    """Base class for slash commands."""

    name: str
    aliases: list[str] = []
    description: str = ""

    @abstractmethod
    def execute(self, args: str, ctx: "SharedContext") -> str:
        """Execute the command and return response string."""
        pass
