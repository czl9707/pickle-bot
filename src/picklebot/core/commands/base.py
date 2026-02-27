"""Base classes for slash commands."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


@dataclass
class CommandResult:
    """Result of executing a slash command."""

    message: str | None = None


class Command(ABC):
    """Base class for slash commands."""

    name: str
    aliases: list[str] = []
    description: str = ""

    @abstractmethod
    def execute(self, args: str, ctx: "SharedContext") -> CommandResult:
        """Execute the command and return result."""
        pass
