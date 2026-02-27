# src/picklebot/core/commands/registry.py
"""Command registry for managing slash commands."""

from typing import TYPE_CHECKING

from picklebot.core.commands.base import Command, CommandResult

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


class CommandRegistry:
    """Registry for slash commands."""

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, cmd: Command) -> None:
        """Register a command and its aliases."""
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._commands[alias] = cmd

    def resolve(self, input: str) -> tuple[Command, str] | None:
        """
        Parse input and return (command, args) if it matches.

        Args:
            input: Full input string (e.g., "/agent" or "/help")

        Returns:
            Tuple of (Command, args_string) or None if no match
        """
        if not input.startswith("/"):
            return None

        parts = input[1:].split(None, 1)
        if not parts:
            return None

        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        cmd = self._commands.get(cmd_name)
        if cmd:
            return (cmd, args)
        return None

    def dispatch(self, input: str, ctx: "SharedContext") -> CommandResult | None:
        """
        Parse and execute a slash command.

        Args:
            input: Full input string
            ctx: SharedContext for accessing loaders

        Returns:
            CommandResult if command matched, None if not a command
        """
        resolved = self.resolve(input)
        if not resolved:
            return None

        cmd, args = resolved
        return cmd.execute(args, ctx)

    @classmethod
    def with_builtins(cls) -> "CommandRegistry":
        """Create registry with built-in commands registered."""
        from picklebot.core.commands.handlers import (
            HelpCommand,
            AgentCommand,
            SkillsCommand,
            CronsCommand,
        )

        registry = cls()
        registry.register(HelpCommand())
        registry.register(AgentCommand())
        registry.register(SkillsCommand())
        registry.register(CronsCommand())
        return registry
