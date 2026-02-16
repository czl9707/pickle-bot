"""Tests for AgentDef model."""

from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.utils.config import LLMConfig


class TestAgentBehaviorConfig:
    def test_defaults(self):
        """Default values for behavior config."""
        config = AgentBehaviorConfig()
        assert config.temperature == 0.7
        assert config.max_tokens == 2048

    def test_custom_values(self):
        """Custom values for behavior config."""
        config = AgentBehaviorConfig(temperature=0.5, max_tokens=4096)
        assert config.temperature == 0.5
        assert config.max_tokens == 4096


class TestAgentDef:
    def test_agent_def_creation(self):
        """Create an AgentDef with all required fields."""
        llm_config = LLMConfig(provider="openai", model="gpt-4", api_key="test-key")
        behavior = AgentBehaviorConfig(temperature=0.8, max_tokens=1024)

        agent_def = AgentDef(
            id="test-agent",
            name="Test Agent",
            system_prompt="You are a test assistant.",
            llm=llm_config,
            behavior=behavior,
        )

        assert agent_def.id == "test-agent"
        assert agent_def.name == "Test Agent"
        assert agent_def.system_prompt == "You are a test assistant."
        assert agent_def.llm.provider == "openai"
        assert agent_def.llm.model == "gpt-4"
        assert agent_def.behavior.temperature == 0.8
        assert agent_def.behavior.max_tokens == 1024

    def test_agent_def_with_default_behavior(self):
        """Create an AgentDef with default behavior config."""
        llm_config = LLMConfig(
            provider="anthropic", model="claude-3-opus", api_key="test-key"
        )

        agent_def = AgentDef(
            id="claude-agent",
            name="Claude Agent",
            system_prompt="You are helpful.",
            llm=llm_config,
            behavior=AgentBehaviorConfig(),
        )

        assert agent_def.behavior.temperature == 0.7
        assert agent_def.behavior.max_tokens == 2048

    def test_agent_def_defaults(self):
        """Test AgentDef has default values."""
        agent_def = AgentDef(
            id="test",
            name="Test Agent",
            system_prompt="You are a test agent",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            behavior=AgentBehaviorConfig(),
        )
        assert agent_def.allow_skills is False
