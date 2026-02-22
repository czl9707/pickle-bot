"""Tests for the Agent class."""

import pytest

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


@pytest.mark.parametrize("mode,expected_history_attr", [
    (SessionMode.CHAT, "chat_max_history"),
    (SessionMode.JOB, "job_max_history"),
])
def test_session_max_history(test_agent, test_config, mode, expected_history_attr):
    """Agent.new_session should use correct max_history based on mode."""
    session = test_agent.new_session(mode)
    assert session.max_history == getattr(test_config, expected_history_attr)


def _create_agent_with_skills(test_config, allow_skills: bool) -> Agent:
    """Helper to create an agent with skills directory set up."""
    skills_path = test_config.skills_path
    skills_path.mkdir(parents=True, exist_ok=True)

    test_skill_dir = skills_path / "test-skill"
    test_skill_dir.mkdir()
    (test_skill_dir / "SKILL.md").write_text(
        "---\nname: Test Skill\ndescription: A test skill\n---\nTest skill content.\n"
    )

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
        allow_skills=allow_skills,
    )
    context = SharedContext(config=test_config)
    return Agent(agent_def=agent_def, context=context)


@pytest.mark.parametrize("allow_skills,expected", [
    (True, True),
    (False, False),
])
def test_skill_tool_registration(test_config, allow_skills, expected):
    """Session should register skill tool based on allow_skills setting."""
    agent = _create_agent_with_skills(test_config, allow_skills)
    session = agent.new_session(SessionMode.CHAT)
    tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]

    assert ("skill" in tool_names) == expected


def _create_agent_with_other_agents(test_config, test_agent_def, has_other_agents: bool) -> Agent:
    """Helper to create an agent optionally with other agents present."""
    if has_other_agents:
        other_agent_dir = test_config.agents_path / "other-agent"
        other_agent_dir.mkdir(parents=True)
        (other_agent_dir / "AGENT.md").write_text(
            "---\nname: Other Agent\ndescription: Another agent for testing\n---\nYou are another agent.\n"
        )

    test_agent_def.description = "Test agent"
    context = SharedContext(config=test_config)
    return Agent(agent_def=test_agent_def, context=context)


@pytest.mark.parametrize("has_other_agents,expected", [
    (True, True),
    (False, False),
])
def test_subagent_dispatch_registration(test_config, test_agent_def, has_other_agents, expected):
    """Session should register subagent_dispatch tool only when other agents exist."""
    agent = _create_agent_with_other_agents(test_config, test_agent_def, has_other_agents)
    session = agent.new_session(SessionMode.CHAT)
    tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]

    assert ("subagent_dispatch" in tool_names) == expected


def _create_agent_with_messagebus(test_config) -> Agent:
    """Helper to create an agent with messagebus enabled."""
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
    return Agent(agent_def=agent_def, context=context)


@pytest.mark.parametrize("mode,expected", [
    (SessionMode.CHAT, False),
    (SessionMode.JOB, True),
])
def test_post_message_availability(test_config, mode, expected):
    """post_message tool should only be available in JOB mode."""
    agent = _create_agent_with_messagebus(test_config)
    session = agent.new_session(mode)
    tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]

    assert ("post_message" in tool_names) == expected
