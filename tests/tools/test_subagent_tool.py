"""Tests for subagent dispatch tool factory."""

import pytest
from pathlib import Path

from picklebot.core.agent_loader import AgentLoader
from picklebot.core.context import SharedContext
from picklebot.tools.subagent_tool import create_subagent_dispatch_tool
from picklebot.utils.config import Config, LLMConfig


class TestCreateSubagentDispatchTool:
    """Tests for create_subagent_dispatch_tool factory function."""

    def test_create_tool_returns_none_when_no_agents(self, tmp_path: Path):
        """create_subagent_dispatch_tool should return None when no agents available."""
        config = self._create_test_config(tmp_path)
        context = SharedContext(config=config)
        loader = context.agent_loader

        tool_func = create_subagent_dispatch_tool(loader, "any-agent", context)
        assert tool_func is None

    def test_tool_has_correct_schema(self, tmp_path: Path):
        """Subagent dispatch tool should have correct name, description, and parameters."""
        config = self._create_test_config(tmp_path)

        # Create multiple agents
        for agent_id, name, desc in [
            ("reviewer", "Code Reviewer", "Reviews code for quality"),
            ("planner", "Task Planner", "Plans and organizes tasks"),
        ]:
            agent_dir = config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

        context = SharedContext(config=config)
        loader = context.agent_loader

        tool_func = create_subagent_dispatch_tool(loader, "caller", context)

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

    def test_tool_excludes_calling_agent(self, tmp_path: Path):
        """Subagent dispatch tool should exclude the calling agent from enum."""
        config = self._create_test_config(tmp_path)

        # Create multiple agents
        for agent_id, name, desc in [
            ("agent-a", "Agent A", "First agent"),
            ("agent-b", "Agent B", "Second agent"),
            ("agent-c", "Agent C", "Third agent"),
        ]:
            agent_dir = config.agents_path / agent_id
            agent_dir.mkdir(parents=True)
            agent_file = agent_dir / "AGENT.md"
            agent_file.write_text(f"""---
name: {name}
description: {desc}
---

You are {name}.
""")

        context = SharedContext(config=config)
        loader = context.agent_loader

        # When agent-b calls the factory, it should be excluded
        tool_func = create_subagent_dispatch_tool(loader, "agent-b", context)

        assert tool_func is not None
        enum_ids = set(tool_func.parameters["properties"]["agent_id"]["enum"])
        assert "agent-a" in enum_ids
        assert "agent-c" in enum_ids
        assert "agent-b" not in enum_ids  # Excluded!

    def _create_test_config(self, tmp_path: Path) -> Config:
        """Create a minimal test config."""
        config_file = tmp_path / "config.system.yaml"
        config_file.write_text("""
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
default_agent: test-agent
""")
        return Config.load(tmp_path)
