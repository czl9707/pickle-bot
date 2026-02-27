# tests/core/commands/test_registry.py
"""Tests for CommandRegistry."""

import pytest

from picklebot.core.commands.base import Command
from picklebot.core.commands.registry import CommandRegistry


class MockCommand(Command):
    """Mock command for testing."""

    name = "mock"
    aliases = ["m"]

    def execute(self, args: str, ctx) -> str:
        return f"mock: {args}"


class TestCommandRegistry:
    """Tests for CommandRegistry."""

    def test_register_stores_by_name_and_aliases(self):
        """register() should store command by name and all aliases."""
        registry = CommandRegistry()
        cmd = MockCommand()
        registry.register(cmd)

        assert registry._commands["mock"] == cmd
        assert registry._commands["m"] == cmd

    @pytest.mark.parametrize(
        "input,expected",
        [
            ("hello world", None),  # no slash
            ("mock", None),  # no slash prefix
            ("/unknown", None),  # unknown command
            ("/mock", ("mock", "")),  # known command
            ("/mock arg1 arg2", ("mock", "arg1 arg2")),  # with args
            ("/m test", ("mock", "test")),  # by alias
            ("/MOCK", ("mock", "")),  # case insensitive
        ],
    )
    def test_resolve(self, input, expected):
        """resolve() should parse input correctly."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = registry.resolve(input)

        if expected is None:
            assert result is None
        else:
            assert result[0].name == expected[0]
            assert result[1] == expected[1]

    @pytest.mark.parametrize(
        "input,expected",
        [
            ("hello", None),
            ("/unknown", None),
            ("/mock test", "mock: test"),
        ],
    )
    def test_dispatch(self, input, expected):
        """dispatch() should execute or return None."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = registry.dispatch(input, None)

        assert result == expected


class TestCommandRegistryWithBuiltins:
    """Tests for with_builtins factory."""

    def test_with_builtins_has_all_commands(self):
        """with_builtins() should have help, agent, skills, crons."""
        registry = CommandRegistry.with_builtins()

        names = {cmd.name for cmd in registry.list_commands()}
        assert names == {"help", "agent", "skills", "crons"}

    def test_with_builtins_has_aliases(self):
        """with_builtins() should register aliases."""
        registry = CommandRegistry.with_builtins()

        assert registry._commands.get("?") is not None
        assert registry._commands.get("agents") is not None

    def test_dispatch_help(self):
        """dispatch /help should return command list."""
        from unittest.mock import MagicMock

        registry = CommandRegistry.with_builtins()
        mock_ctx = MagicMock()
        mock_ctx.command_registry = registry

        result = registry.dispatch("/help", mock_ctx)

        assert "Available Commands" in result
