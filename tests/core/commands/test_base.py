"""Tests for command base classes."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from picklebot.core.commands.base import Command

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession


class ConcreteCommand(Command):
    """Concrete implementation for testing."""

    name = "test"
    aliases = ["t", "tst"]
    description = "A test command"

    async def execute(self, args: str, session: "AgentSession") -> str:
        return f"executed with: {args}, session: {session.session_id}"


class MockCommand(Command):
    """Test command implementation."""

    name = "test"
    description = "Test command"

    async def execute(self, args: str, session: "AgentSession") -> str:
        return f"Executed with session: {session.session_id}"


@pytest.fixture
def mock_session():
    """Create a mock AgentSession for testing with all required properties."""
    session = MagicMock()
    session.session_id = "session-123"
    session.shared_context = MagicMock()
    session.source = MagicMock()
    return session


class TestCommand:
    """Tests for Command ABC."""

    @pytest.mark.anyio
    async def test_command_creation_and_execution(self, mock_session):
        """Command should have properties and execute correctly."""
        cmd = ConcreteCommand()

        # Check properties
        assert cmd.name == "test"
        assert cmd.aliases == ["t", "tst"]
        assert cmd.description == "A test command"

        # Check execution with session parameter
        result = await cmd.execute("args", mock_session)
        assert "args" in result
        assert mock_session.session_id in result

    @pytest.mark.anyio
    async def test_command_execute_receives_session(self, mock_session):
        """Test that execute receives AgentSession with expected properties."""
        cmd = MockCommand()

        result = await cmd.execute("test-args", mock_session)

        # Verify session_id is used correctly
        assert "session-" in result
        assert mock_session.session_id in result

        # Verify AgentSession-like properties exist on mock
        assert hasattr(mock_session, "session_id")
        assert hasattr(mock_session, "shared_context")
        assert hasattr(mock_session, "source")

        # Verify properties are not None
        assert mock_session.session_id is not None
        assert mock_session.shared_context is not None
        assert mock_session.source is not None
