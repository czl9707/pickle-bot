"""Tests for command base classes."""

from picklebot.core.commands.base import Command


class ConcreteCommand(Command):
    """Concrete implementation for testing."""

    name = "test"
    aliases = ["t", "tst"]
    description = "A test command"

    def execute(self, args: str, ctx) -> str:
        return f"executed with: {args}"


class TestCommand:
    """Tests for Command ABC."""

    def test_command_properties(self):
        """Command should have name, aliases, description."""
        cmd = ConcreteCommand()
        assert cmd.name == "test"
        assert cmd.aliases == ["t", "tst"]
        assert cmd.description == "A test command"

    def test_execute_returns_string(self):
        """execute() should return string."""
        cmd = ConcreteCommand()
        assert cmd.execute("args", None) == "executed with: args"
