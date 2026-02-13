"""Tests for ToolRegistry."""

from picklebot.tools.registry import ToolRegistry


def test_tool_registry_with_builtins_creates_registry_with_tools():
    """with_builtins() should create registry with builtin tools registered."""
    registry = ToolRegistry.with_builtins()

    # Should have at least one builtin tool
    assert len(registry._tools) > 0
