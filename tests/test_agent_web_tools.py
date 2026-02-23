"""Tests for agent loading web tools."""

import pytest

from picklebot.core.agent import Agent, SessionMode
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import (
    Config,
    LLMConfig,
    BraveWebSearchConfig,
    Crawl4AIWebReadConfig,
)


@pytest.fixture
def web_test_config(tmp_path):
    """Config with workspace pointing to tmp_path."""
    return Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        default_agent="test",
    )


class TestAgentWebTools:
    """Tests for agent loading web tools when configured."""

    def test_agent_loads_websearch_when_configured(self, web_test_config):
        """Agent should load websearch tool when config.websearch is set."""
        web_test_config.websearch = BraveWebSearchConfig(api_key="test-key")
        agent_def = AgentDef(
            id="test-agent",
            name="Test Agent",
            system_prompt="You are a test assistant.",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        )
        context = SharedContext(config=web_test_config)

        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=SessionMode.CHAT)
        tool_names = list(registry._tools.keys())

        assert "websearch" in tool_names

    def test_agent_loads_webread_when_configured(self, web_test_config):
        """Agent should load webread tool when config.webread is set."""
        web_test_config.webread = Crawl4AIWebReadConfig()
        agent_def = AgentDef(
            id="test-agent",
            name="Test Agent",
            system_prompt="You are a test assistant.",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        )
        context = SharedContext(config=web_test_config)

        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=SessionMode.CHAT)
        tool_names = list(registry._tools.keys())

        assert "webread" in tool_names

    def test_agent_skips_websearch_when_not_configured(self, web_test_config):
        """Agent should not load websearch tool when not configured."""
        web_test_config.websearch = None
        agent_def = AgentDef(
            id="test-agent",
            name="Test Agent",
            system_prompt="You are a test assistant.",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        )
        context = SharedContext(config=web_test_config)

        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=SessionMode.CHAT)
        tool_names = list(registry._tools.keys())

        assert "websearch" not in tool_names

    def test_agent_skips_webread_when_not_configured(self, web_test_config):
        """Agent should not load webread tool when not configured."""
        web_test_config.webread = None
        agent_def = AgentDef(
            id="test-agent",
            name="Test Agent",
            system_prompt="You are a test assistant.",
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        )
        context = SharedContext(config=web_test_config)

        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=SessionMode.CHAT)
        tool_names = list(registry._tools.keys())

        assert "webread" not in tool_names
