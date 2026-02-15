"""Tests for the Agent class."""

from pathlib import Path
from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.core.agent_def import AgentDef, AgentBehaviorConfig
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import Config, LLMConfig
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
default_agent: test-agent
"""
    )
    return Config.load(tmp_path)


def _create_test_agent_def() -> AgentDef:
    """Create a minimal test agent definition."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )


def test_agent_creation_with_new_structure(tmp_path: Path) -> None:
    """Agent should be created with agent_def, llm, tools, context."""
    config = _create_test_config(tmp_path)
    context = SharedContext(config=config)
    agent_def = _create_test_agent_def()

    agent = Agent(
        agent_def=agent_def,
        llm=LLMProvider.from_config(agent_def.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )

    assert agent.agent_def is agent_def
    assert agent.context is context


def test_agent_new_session(tmp_path: Path) -> None:
    """Agent should create new session with self reference."""
    config = _create_test_config(tmp_path)
    context = SharedContext(config=config)
    agent_def = _create_test_agent_def()

    agent = Agent(
        agent_def=agent_def,
        llm=LLMProvider.from_config(agent_def.llm),
        tools=ToolRegistry.with_builtins(),
        context=context,
    )

    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == agent_def.id
    assert session.agent is agent
