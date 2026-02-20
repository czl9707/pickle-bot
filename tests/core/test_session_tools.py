"""Tests for session-scoped tool registration."""

from picklebot.core.agent import Agent, SessionMode
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import LLMConfig, MessageBusConfig, TelegramConfig


def test_session_has_tools_attribute(test_agent):
    """Session should have a tools attribute."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert hasattr(session, "tools")
    assert session.tools is not None


def test_session_has_mode_attribute(test_agent):
    """Session should store its mode."""
    session = test_agent.new_session(SessionMode.CHAT)

    assert session.mode == SessionMode.CHAT


def test_session_has_own_tool_registry(test_agent):
    """Session should have its own ToolRegistry instance."""
    session1 = test_agent.new_session(SessionMode.CHAT)
    session2 = test_agent.new_session(SessionMode.CHAT)

    # Each session should have its own registry
    assert session1.tools is not session2.tools


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
