"""Tests for AgentDef model."""

from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.utils.config import LLMConfig


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
