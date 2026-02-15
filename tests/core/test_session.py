from pathlib import Path

from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.core.agent_loader import AgentDef, AgentBehaviorConfig
from picklebot.utils.config import Config, LLMConfig


def _create_test_agent(tmp_path: Path) -> Agent:
    """Create a minimal test agent."""
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
    config = Config.load(tmp_path)
    context = SharedContext(config=config)

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        system_prompt="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        behavior=AgentBehaviorConfig(),
    )

    return Agent(agent_def=agent_def, context=context)


def test_session_creation(tmp_path):
    """Session should be created with required fields including agent."""
    agent = _create_test_agent(tmp_path)
    session = agent.new_session()

    assert session.session_id is not None
    assert session.agent_id == agent.agent_def.id
    assert session.agent is agent
    assert session.messages == []


def test_session_add_message(tmp_path):
    """Session should add message to in-memory list and persist to history."""
    agent = _create_test_agent(tmp_path)
    session = agent.new_session()

    session.add_message({"role": "user", "content": "Hello"})

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"

    # Verify persisted
    messages = agent.context.history_store.get_messages(session.session_id)
    assert len(messages) == 1
    assert messages[0].content == "Hello"


def test_session_get_history_limits_messages(tmp_path):
    """Session should limit history to max_messages."""
    agent = _create_test_agent(tmp_path)
    session = agent.new_session()

    # Add 5 messages
    for i in range(5):
        session.add_message({"role": "user", "content": f"Message {i}"})

    history = session.get_history(max_messages=3)

    assert len(history) == 3
    assert history[0]["content"] == "Message 2"  # Last 3 messages
