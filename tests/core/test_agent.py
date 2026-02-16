"""Tests for the Agent class."""

from pathlib import Path
from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.core.agent_loader import AgentDef, AgentBehaviorConfig
from picklebot.utils.config import Config, LLMConfig


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
        description="A test agent for unit testing",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )


def test_agent_creation_with_new_structure(tmp_path: Path) -> None:
    """Agent should be created with agent_def, llm, tools, context."""
    config = _create_test_config(tmp_path)
    context = SharedContext(config=config)
    agent_def = _create_test_agent_def()

    agent = Agent(agent_def=agent_def, context=context)

    assert agent.agent_def is agent_def
    assert agent.context is context


def test_agent_new_session(tmp_path: Path) -> None:
    """Agent should create new session with self reference."""
    config = _create_test_config(tmp_path)
    context = SharedContext(config=config)
    agent_def = _create_test_agent_def()

    agent = Agent(agent_def=agent_def, context=context)

    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == agent_def.id
    assert session.agent is agent


def test_agent_registers_skill_tool_when_allowed(tmp_path: Path) -> None:
    """Agent should register skill tool when allow_skills is True and skills exist."""
    # Create test config with skills directory
    config = _create_test_config(tmp_path)
    skills_path = tmp_path / "skills"
    skills_path.mkdir()
    config.skills_path = skills_path

    # Create a test skill
    test_skill_dir = skills_path / "test-skill"
    test_skill_dir.mkdir()
    skill_file = test_skill_dir / "SKILL.md"
    skill_file.write_text(
        """---
name: Test Skill
description: A test skill
---

Test skill content.
"""
    )

    # Create agent with allow_skills=True
    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=True,
    )
    context = SharedContext(config=config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" in tool_names


def test_agent_skips_skill_tool_when_not_allowed(tmp_path: Path) -> None:
    """Agent should NOT register skill tool when allow_skills is False."""
    # Create test config with skills directory
    config = _create_test_config(tmp_path)
    skills_path = tmp_path / "skills"
    skills_path.mkdir()
    config.skills_path = skills_path

    # Create a test skill (but it shouldn't be loaded)
    test_skill_dir = skills_path / "test-skill"
    test_skill_dir.mkdir()
    skill_file = test_skill_dir / "SKILL.md"
    skill_file.write_text(
        """---
name: Test Skill
description: A test skill
---

Test skill content.
"""
    )

    # Create agent with allow_skills=False (default)
    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=False,
    )
    context = SharedContext(config=config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" not in tool_names


def test_agent_registers_subagent_dispatch_tool(tmp_path: Path) -> None:
    """Agent should always register subagent_dispatch tool when other agents exist."""
    config = _create_test_config(tmp_path)

    # Create another agent (so dispatch tool has something to dispatch to)
    other_agent_dir = config.agents_path / "other-agent"
    other_agent_dir.mkdir(parents=True)
    other_agent_file = other_agent_dir / "AGENT.md"
    other_agent_file.write_text("""---
name: Other Agent
description: Another agent for testing
---

You are another agent.
""")

    agent_def = _create_test_agent_def()
    agent_def.description = "Test agent"  # Add description
    context = SharedContext(config=config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that subagent_dispatch tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" in tool_names


def test_agent_skips_subagent_dispatch_when_no_other_agents(tmp_path: Path) -> None:
    """Agent should NOT register subagent_dispatch tool when no other agents exist."""
    config = _create_test_config(tmp_path)
    # Don't create any other agents

    agent_def = _create_test_agent_def()
    agent_def.description = "Test agent"
    context = SharedContext(config=config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that subagent_dispatch tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" not in tool_names
