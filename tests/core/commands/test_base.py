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

    def test_command_creation_and_execution(self):
        """Command should have properties and execute correctly."""
        cmd = ConcreteCommand()

        # Check properties
        assert cmd.name == "test"
        assert cmd.aliases == ["t", "tst"]
        assert cmd.description == "A test command"

        # Check execution
        assert cmd.execute("args", None) == "executed with: args"
