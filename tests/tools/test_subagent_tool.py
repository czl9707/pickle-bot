"""Tests for subagent dispatch tool factory."""

import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from picklebot.core.context import SharedContext
from picklebot.frontend.base import SilentFrontend
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool


class TestCreateSubagentDispatchTool:
    """Tests for create_subagent_dispatch_tool factory function."""

    def test_create_tool_returns_none_when_no_agents(self, test_config):
        """create_subagent_dispatch_tool should return None when no agents available."""
        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("any-agent", context)
        assert tool_func is None

    def test_tool_has_correct_schema(self, test_config):
        """Subagent dispatch tool should have correct name, description, and parameters."""
        # Create multiple agents
        for agent_id, name, desc in [
            ("reviewer", "Code Reviewer", "Reviews code for quality"),
            ("planner", "Task Planner", "Plans and organizes tasks"),
        ]:
            agent_dir = test_config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(
                f"""---
name: {name}
description: {desc}
---

You are {name}.
"""
            )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)

        assert tool_func is not None
        # Check tool properties
        assert tool_func.name == "subagent_dispatch"
        assert "Dispatch a task to a specialized subagent" in tool_func.description
        assert "<available_agents>" in tool_func.description
        assert 'id="reviewer"' in tool_func.description
        assert "Reviews code for quality" in tool_func.description
        assert 'id="planner"' in tool_func.description

        # Check parameters schema
        params = tool_func.parameters
        assert params["type"] == "object"
        assert "agent_id" in params["properties"]
        assert params["properties"]["agent_id"]["type"] == "string"
        assert set(params["properties"]["agent_id"]["enum"]) == {"reviewer", "planner"}
        assert "task" in params["properties"]
        assert "context" in params["properties"]
        assert params["required"] == ["agent_id", "task"]

    def test_tool_excludes_calling_agent(self, test_config):
        """Subagent dispatch tool should exclude the calling agent from enum."""
        # Create multiple agents
        for agent_id, name, desc in [
            ("agent-a", "Agent A", "First agent"),
            ("agent-b", "Agent B", "Second agent"),
            ("agent-c", "Agent C", "Third agent"),
        ]:
            agent_dir = test_config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(
                f"""---
name: {name}
description: {desc}
---

You are {name}.
"""
            )

        context = SharedContext(config=test_config)

        # When agent-b calls the factory, it should be excluded
        tool_func = create_subagent_dispatch_tool("agent-b", context)

        assert tool_func is not None
        enum_ids = set(tool_func.parameters["properties"]["agent_id"]["enum"])
        assert "agent-a" in enum_ids
        assert "agent-c" in enum_ids
        assert "agent-b" not in enum_ids  # Excluded!

    @pytest.mark.anyio
    async def test_tool_dispatches_to_subagent(self, test_config):
        """Subagent dispatch tool should create session and return result + session_id."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(
            """---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
"""
        )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        # Simpler approach: mock Agent and Session
        mock_response = "Task completed successfully"

        with patch("picklebot.core.agent.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-123"
            mock_session.chat = AsyncMock(return_value=mock_response)

            # Execute
            frontend = SilentFrontend()
            result = await tool_func.execute(
                frontend=frontend, agent_id="target-agent", task="Do something"
            )

            # Verify
            parsed = json.loads(result)
            assert parsed["result"] == "Task completed successfully"
            assert parsed["session_id"] == "test-session-123"

            # Verify session.chat was called with correct message
            mock_session.chat.assert_called_once_with("Do something", ANY)

    @pytest.mark.anyio
    async def test_tool_includes_context_in_message(self, test_config):
        """Subagent dispatch tool should include context in user message."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(
            """---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
"""
        )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        with patch("picklebot.core.agent.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-456"
            mock_session.chat = AsyncMock(return_value="Done")

            # Execute with context
            frontend = SilentFrontend()
            await tool_func.execute(
                frontend=frontend,
                agent_id="target-agent",
                task="Review this",
                context="The code is in src/main.py",
            )

            # Verify context was included
            mock_session.chat.assert_called_once()
            call_args = mock_session.chat.call_args
            message = call_args[0][0]
            assert "Review this" in message
            assert "Context:" in message
            assert "The code is in src/main.py" in message


class TestSubagentDispatchFrontendCalls:
    """Tests for subagent dispatch frontend method calls."""

    @pytest.mark.anyio
    async def test_subagent_dispatch_calls_show_dispatch(self, test_config):
        """Subagent dispatch tool should call frontend.show_dispatch() context manager."""
        # Create target agent
        agent_dir = test_config.agents_path / "target-agent"
        agent_dir.mkdir(parents=True)
        agent_file = agent_dir / "AGENT.md"
        agent_file.write_text(
            """---
name: Target Agent
description: A target for dispatch testing
---

You are the target agent.
"""
        )

        context = SharedContext(config=test_config)

        tool_func = create_subagent_dispatch_tool("caller", context)
        assert tool_func is not None

        # Use a mock frontend to track calls
        mock_frontend = MagicMock(spec=SilentFrontend)
        # Setup async context manager mock
        mock_dispatch_context = AsyncMock()
        mock_dispatch_context.__aenter__ = AsyncMock(return_value=None)
        mock_dispatch_context.__aexit__ = AsyncMock(return_value=None)
        mock_frontend.show_dispatch.return_value = mock_dispatch_context

        with patch("picklebot.core.agent.Agent") as mock_agent_class:
            mock_agent = mock_agent_class.return_value
            mock_session = mock_agent.new_session.return_value
            mock_session.session_id = "test-session-789"
            mock_session.chat = AsyncMock(return_value="Task done")

            # Execute
            await tool_func.execute(
                frontend=mock_frontend,
                agent_id="target-agent",
                task="Do something",
            )

            # Verify show_dispatch was called with correct args
            mock_frontend.show_dispatch.assert_called_once()
            call_args = mock_frontend.show_dispatch.call_args
            # Verify calling agent, target agent, and task are passed
            assert call_args[0][0] == "caller"  # calling agent
            assert call_args[0][1] == "target-agent"  # target agent
            assert call_args[0][2] == "Do something"  # task
