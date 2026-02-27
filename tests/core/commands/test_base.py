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

    def test_command_has_name(self):
        """Command should have a name attribute."""
        cmd = ConcreteCommand()
        assert cmd.name == "test"

    def test_command_has_aliases(self):
        """Command should have aliases attribute."""
        cmd = ConcreteCommand()
        assert cmd.aliases == ["t", "tst"]

    def test_command_has_description(self):
        """Command should have description attribute."""
        cmd = ConcreteCommand()
        assert cmd.description == "A test command"

    def test_execute_returns_string(self):
        """execute() should return string."""
        cmd = ConcreteCommand()
        result = cmd.execute("arg1 arg2", None)
        assert isinstance(result, str)
        assert result == "executed with: arg1 arg2"
