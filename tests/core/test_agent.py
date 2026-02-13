"""Tests for the Agent class."""

from pathlib import Path
from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import Config
from picklebot.provider import LLMProvider


def _create_test_config(tmp_path: Path) -> Config:
    """Create a minimal test config file."""
    config_file = tmp_path / "config.system.yaml"
    config_file.write_text(
        """
llm:
  provider: openai
  model: gpt-4
  api_key: test-key
"""
    )
    return Config.load(tmp_path)


def test_agent_creation_with_new_structure(tmp_path: Path) -> None:
    """Agent should be created with agent_config, llm, tools, context."""
    config = _create_test_config(tmp_path)
    context = SharedContext(config=config)

    agent = Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )

    assert agent.agent_config is config.agent
    assert agent.context is context


def test_agent_new_session(tmp_path: Path) -> None:
    """Agent should create new session with self reference."""
    config = _create_test_config(tmp_path)
    context = SharedContext(config=config)

    agent = Agent(
        agent_config=config.agent,
        llm=LLMProvider.from_config(config.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )

    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == config.agent.name
    assert session.agent is agent
