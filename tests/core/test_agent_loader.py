"""Tests for AgentLoader."""

import pytest
from picklebot.core.agent_loader import AgentNotFoundError, InvalidAgentError


class TestExceptions:
    def test_agent_not_found_error(self):
        """AgentNotFoundError includes agent_id."""
        error = AgentNotFoundError("pickle")
        assert "pickle" in str(error)
        assert error.agent_id == "pickle"

    def test_invalid_agent_error(self):
        """InvalidAgentError includes agent_id and reason."""
        error = InvalidAgentError("pickle", "missing name field")
        assert "pickle" in str(error)
        assert "missing name field" in str(error)
        assert error.agent_id == "pickle"
        assert error.reason == "missing name field"
