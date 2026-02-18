"""Tests for the Agent class."""

from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import LLMConfig


def test_agent_creation_with_new_structure(test_agent, test_agent_def, test_context):
    """Agent should be created with agent_def, llm, tools, context."""
    assert test_agent.agent_def is test_agent_def
    assert test_agent.context is test_context


def test_agent_new_session(test_agent, test_agent_def):
    """Agent should create new session with self reference."""
    session = test_agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == test_agent_def.id
    assert session.agent is test_agent


def test_agent_registers_skill_tool_when_allowed(test_config):
    """Agent should register skill tool when allow_skills is True and skills exist."""
    # Create skills directory
    skills_path = test_config.skills_path
    skills_path.mkdir(parents=True, exist_ok=True)

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
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" in tool_names


def test_agent_skips_skill_tool_when_not_allowed(test_config):
    """Agent should NOT register skill tool when allow_skills is False."""
    # Create skills directory
    skills_path = test_config.skills_path
    skills_path.mkdir(parents=True, exist_ok=True)

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
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    # Check that skill tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" not in tool_names


def test_agent_registers_subagent_dispatch_tool(test_config, test_agent_def):
    """Agent should always register subagent_dispatch tool when other agents exist."""
    # Create another agent (so dispatch tool has something to dispatch to)
    other_agent_dir = test_config.agents_path / "other-agent"
    other_agent_dir.mkdir(parents=True)
    other_agent_file = other_agent_dir / "AGENT.md"
    other_agent_file.write_text("""---
name: Other Agent
description: Another agent for testing
---

You are another agent.
""")

    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" in tool_names


def test_agent_skips_subagent_dispatch_when_no_other_agents(test_config, test_agent_def):
    """Agent should NOT register subagent_dispatch tool when no other agents exist."""
    # Don't create any other agents
    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is NOT registered
    tool_schemas = agent.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" not in tool_names
