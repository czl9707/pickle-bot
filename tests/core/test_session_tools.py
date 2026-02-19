"""Tests for session-scoped tool registration."""

from picklebot.core.agent import SessionMode


def test_session_has_tools_attribute(test_agent):
    """Session should have a tools attribute."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert hasattr(session, "tools")
    assert session.tools is not None


def test_session_has_mode_attribute(test_agent):
    """Session should store its mode."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.mode == SessionMode.CHAT


def test_session_has_own_tool_registry(test_agent):
    """Session should have its own ToolRegistry instance."""
    session1 = test_agent.new_session(SessionMode.CHAT)
    session2 = test_agent.new_session(SessionMode.CHAT)

    # Each session should have its own registry
    assert session1.tools is not session2.tools
