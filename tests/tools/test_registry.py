"""Tests for ToolRegistry."""

import pytest
from unittest.mock import MagicMock

from picklebot.tools.registry import ToolRegistry
from picklebot.tools.base import BaseTool


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"
    parameters = {"type": "object", "properties": {}}

    def __init__(self):
        self.last_kwargs = None
        self.last_session = None

    async def execute(self, session, **kwargs):
        """Execute mock tool, store kwargs for verification."""
        self.last_session = session
        self.last_kwargs = kwargs
        return "mock result"


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_register_tool(self):
        """register() should add tool to registry."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        assert registry.get("mock_tool") == tool

    def test_get_nonexistent_tool(self):
        """get() should return None for nonexistent tool."""
        registry = ToolRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_list_all(self):
        """list_all() should return all registered tools."""
        registry = ToolRegistry()
        tool1 = MockTool()
        tool2 = MockTool()
        tool2.name = "mock_tool_2"

        registry.register(tool1)
        registry.register(tool2)

        tools = registry.list_all()

        assert len(tools) == 2
        assert tool1 in tools
        assert tool2 in tools

    def test_get_tool_schemas(self):
        """get_tool_schemas() should return schemas for all tools."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        schemas = registry.get_tool_schemas()

        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "mock_tool"

    @pytest.mark.anyio
    async def test_execute_tool_passes_kwargs_to_tool(self):
        """execute_tool() should pass kwargs and session to tool."""
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        mock_session = MagicMock()
        result = await registry.execute_tool(
            "mock_tool", session=mock_session, arg1="value1"
        )

        # Verify tool received the kwargs and session
        assert tool.last_kwargs == {"arg1": "value1"}
        assert tool.last_session == mock_session
        assert result == "mock result"

    @pytest.mark.anyio
    async def test_execute_tool_raises_for_nonexistent_tool(self):
        """execute_tool() should raise ValueError for nonexistent tool."""
        registry = ToolRegistry()
        mock_session = MagicMock()

        with pytest.raises(ValueError, match="Tool not found"):
            await registry.execute_tool("nonexistent", session=mock_session)


class TestToolRegistryWithBuiltins:
    """Tests for ToolRegistry.with_builtins() factory."""

    def test_with_builtins_creates_registry_with_builtin_tools(self):
        """with_builtins() should create registry with read, write, edit, bash."""
        registry = ToolRegistry.with_builtins()

        assert registry.get("read") is not None
        assert registry.get("write") is not None
        assert registry.get("edit") is not None
        assert registry.get("bash") is not None

    def test_with_builtins_has_correct_tool_count(self):
        """with_builtins() should register exactly 4 tools."""
        registry = ToolRegistry.with_builtins()

        tools = registry.list_all()

        assert len(tools) == 4
