# tests/core/commands/test_registry.py
"""Tests for CommandRegistry."""

import pytest

from picklebot.core.commands.base import Command
from picklebot.core.commands.registry import CommandRegistry


class MockCommand(Command):
    """Mock command for testing."""

    name = "mock"
    aliases = ["m"]

    async def execute(self, args: str, session) -> str:
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
    async def test_dispatch(self, input, expected):
        """dispatch() should execute or return None."""
        registry = CommandRegistry()
        registry.register(MockCommand())

        result = await registry.dispatch(input, None)

        assert result == expected


class TestCommandRegistryWithBuiltins:
    """Tests for with_builtins factory."""

    def test_with_builtins_has_all_commands(self):
        """Test with_builtins creates registry with builtin commands."""
        registry = CommandRegistry.with_builtins()

        # Should have all 10 commands
        names = {cmd.name for cmd in registry.list_commands()}
        assert names == {
            "help",
            "agent",
            "skills",
            "crons",
            "compact",
            "context",
            "clear",
            "session",
            "route",
            "bindings",
        }

    def test_with_builtins_has_aliases(self):
        """with_builtins() should register aliases."""
        registry = CommandRegistry.with_builtins()

        assert registry._commands.get("?") is not None
        assert registry._commands.get("agents") is not None

    async def test_dispatch_help(self, mock_context):
        """dispatch /help should return command list."""
        from unittest.mock import MagicMock

        registry = CommandRegistry.with_builtins()
        mock_session = MagicMock()
        mock_session.shared_context = mock_context
        mock_context.command_registry = registry

        result = await registry.dispatch("/help", mock_session)

        assert "Available Commands" in result

    async def test_dispatch_with_session(self, mock_context):
        """Test dispatch with AgentSession."""
        from unittest.mock import MagicMock

        registry = CommandRegistry.with_builtins()
        mock_session = MagicMock()
        mock_session.shared_context = mock_context
        mock_context.command_registry = registry

        result = await registry.dispatch("/help", mock_session)

        assert result is not None
        assert "**Available Commands:**" in result

    async def test_dispatch_non_command_returns_none(self):
        """Test dispatch returns None for non-command input."""
        from unittest.mock import MagicMock

        registry = CommandRegistry()
        mock_session = MagicMock()

        result = await registry.dispatch("regular message", mock_session)

        assert result is None
