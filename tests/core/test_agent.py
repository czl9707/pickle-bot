"""Tests for the Agent class."""

from picklebot.core.agent import Agent, SessionMode
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import LLMConfig, MessageBusConfig, TelegramConfig


def test_agent_creation_with_new_structure(test_agent, test_agent_def, test_context):
    """Agent should be created with agent_def, llm, tools, context."""
    assert test_agent.agent_def is test_agent_def
    assert test_agent.context is test_context


def test_agent_new_session(test_agent, test_agent_def):
    """Agent should create new session with self reference and correct mode defaults."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.session_id is not None
    assert session.agent_id == test_agent_def.id
    assert session.agent is test_agent
    assert session.max_history == 50  # chat default


def test_agent_new_session_job_mode(test_agent, test_config):
    """Agent.new_session with JOB mode should use job_max_history."""
    session = test_agent.new_session(SessionMode.JOB)

    assert session.max_history == test_config.job_max_history


def test_agent_new_session_chat_mode(test_agent, test_config):
    """Agent.new_session with CHAT mode should use chat_max_history."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.max_history == test_config.chat_max_history


def test_session_registers_skill_tool_when_allowed(test_config):
    """Session should register skill tool when allow_skills is True and skills exist."""
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

    # Check that skill tool is registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" in tool_names


def test_session_skips_skill_tool_when_not_allowed(test_config):
    """Session should NOT register skill tool when allow_skills is False."""
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

    # Check that skill tool is NOT registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "skill" not in tool_names


def test_session_registers_subagent_dispatch_tool(test_config, test_agent_def):
    """Session should always register subagent_dispatch tool when other agents exist."""
    # Create another agent (so dispatch tool has something to dispatch to)
    other_agent_dir = test_config.agents_path / "other-agent"
    other_agent_dir.mkdir(parents=True)
    other_agent_file = other_agent_dir / "AGENT.md"
    other_agent_file.write_text(
        """---
name: Other Agent
description: Another agent for testing
---

You are another agent.
"""
    )

    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" in tool_names


def test_session_skips_subagent_dispatch_when_no_other_agents(
    test_config, test_agent_def
):
    """Session should NOT register subagent_dispatch tool when no other agents exist."""
    # Don't create any other agents
    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=test_agent_def, context=context)

    # Check that subagent_dispatch tool is NOT registered in session
    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "subagent_dispatch" not in tool_names


def test_post_message_not_available_in_chat_mode(test_config):
    """post_message tool should NOT be available in CHAT mode."""
    # Enable messagebus to make post_message tool possible
    test_config.messagebus = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["123"],
            default_chat_id="123",
        ),
    )

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    session = agent.new_session(SessionMode.CHAT)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "post_message" not in tool_names


def test_post_message_available_in_job_mode(test_config):
    """post_message tool should be available in JOB mode."""
    # Enable messagebus to make post_message tool possible
    test_config.messagebus = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["123"],
            default_chat_id="123",
        ),
    )

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )
    context = SharedContext(config=test_config)
    agent = Agent(agent_def=agent_def, context=context)

    session = agent.new_session(SessionMode.JOB)
    tool_schemas = session.tools.get_tool_schemas()
    tool_names = [schema["function"]["name"] for schema in tool_schemas]

    assert "post_message" in tool_names
