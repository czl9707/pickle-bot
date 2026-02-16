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
