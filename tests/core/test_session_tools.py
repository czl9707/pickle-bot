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
