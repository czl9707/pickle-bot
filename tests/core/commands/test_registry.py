# tests/core/commands/test_registry.py
"""Tests for CommandRegistry."""

from picklebot.core.commands.base import Command
from picklebot.core.commands.registry import CommandRegistry


class MockCommand(Command):
    """Mock command for testing."""

    name = "mock"
    aliases = ["m"]

    def execute(self, args: str, ctx) -> str:
        return f"mock: {args}"


class MockCommand2(Command):
    """Another mock command."""

    name = "other"
    aliases = ["o", "alt"]

    def execute(self, args: str, ctx) -> str:
        return f"other: {args}"


class TestCommandRegistry:
    """Tests for CommandRegistry."""

    def test_register_command(self):
        """register() should add command by name."""
        registry = CommandRegistry()
        cmd = MockCommand()

        registry.register(cmd)

        assert registry._commands["mock"] == cmd

    def test_register_command_aliases(self):
        """register() should add command under all aliases."""
        registry = CommandRegistry()
        cmd = MockCommand()

        registry.register(cmd)

        assert registry._commands["m"] == cmd

    def test_resolve_non_command_returns_none(self):
        """resolve() should return None for non-slash input."""
        registry = CommandRegistry()

        result = registry.resolve("hello world")

        assert result is None

    def test_resolve_without_slash_prefix_returns_none(self):
        """resolve() should return None if no slash prefix."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = registry.resolve("mock")

        assert result is None

    def test_resolve_unknown_command_returns_none(self):
        """resolve() should return None for unknown command."""
        registry = CommandRegistry()

        result = registry.resolve("/unknown")

        assert result is None

    def test_resolve_known_command(self):
        """resolve() should return (command, args) for known command."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/mock")

        assert result == (cmd, "")

    def test_resolve_with_args(self):
        """resolve() should split command and args."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/mock arg1 arg2")

        assert result == (cmd, "arg1 arg2")

    def test_resolve_by_alias(self):
        """resolve() should work with aliases."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/m test")

        assert result == (cmd, "test")

    def test_resolve_case_insensitive(self):
        """resolve() should be case insensitive."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        result = registry.resolve("/MOCK")

        assert result == (cmd, "")

    def test_dispatch_returns_none_for_non_command(self):
        """dispatch() should return None for non-slash input."""
        registry = CommandRegistry()

        result = registry.dispatch("hello", None)

        assert result is None

    def test_dispatch_executes_command(self):
        """dispatch() should execute command and return result string."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = registry.dispatch("/mock test", None)

        assert result == "mock: test"

    def test_dispatch_unknown_returns_none(self):
        """dispatch() should return None for unknown command."""
        registry = CommandRegistry()

        result = registry.dispatch("/unknown", None)

        assert result is None


class TestCommandRegistryWithBuiltins:
    """Tests for with_builtins factory."""

    def test_with_builtins_creates_registry(self):
        """with_builtins() should create registry with all commands."""
        registry = CommandRegistry.with_builtins()

        assert registry._commands.get("help") is not None
        assert registry._commands.get("agent") is not None
        assert registry._commands.get("skills") is not None
        assert registry._commands.get("crons") is not None

    def test_with_builtins_includes_aliases(self):
        """with_builtins() should register aliases."""
        registry = CommandRegistry.with_builtins()

        assert registry._commands.get("?") is not None  # help alias
        assert registry._commands.get("agents") is not None  # agent alias

    def test_with_builtins_dispatch_help(self):
        """with_builtins() registry should dispatch /help."""
        from unittest.mock import MagicMock

        registry = CommandRegistry.with_builtins()
        mock_ctx = MagicMock()
        mock_ctx.command_registry = registry

        result = registry.dispatch("/help", mock_ctx)

        assert result is not None
        assert "Available Commands" in result
