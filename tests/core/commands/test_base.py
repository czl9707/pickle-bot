"""Tests for command base classes."""

from unittest.mock import MagicMock

import pytest

from picklebot.core.commands.base import Command


class ConcreteCommand(Command):
    """Concrete implementation for testing."""

    name = "test"
    aliases = ["t", "tst"]
    description = "A test command"

    def execute(self, args: str, ctx) -> str:
        return f"executed with: {args}"


class MockCommand(Command):
    """Test command implementation."""

    name = "test"
    description = "Test command"

    def execute(self, args: str, session) -> str:
        return f"Executed with session: {session.session_id}"


@pytest.fixture
def mock_session():
    """Create a mock AgentSession for testing."""
    session = MagicMock()
    session.session_id = "session-123"
    return session


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

    def test_command_execute_receives_session(self, mock_session):
        """Test that execute receives AgentSession."""
        cmd = MockCommand()

        result = cmd.execute("test-args", mock_session)

        assert "session-" in result
        assert mock_session.session_id in result
