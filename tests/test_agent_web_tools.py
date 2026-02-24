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

    @pytest.mark.parametrize(
        "tool_name,config_factory,should_exist",
        [
            ("websearch", lambda: BraveWebSearchConfig(api_key="test-key"), True),
            ("websearch", lambda: None, False),
            ("webread", lambda: Crawl4AIWebReadConfig(), True),
            ("webread", lambda: None, False),
        ],
    )
    def test_agent_web_tool_loading(
        self, web_test_config, tool_name, config_factory, should_exist
    ):
        """Agent should load web tools when configured, skip when not."""
        setattr(web_test_config, tool_name, config_factory())

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

        if should_exist:
            assert tool_name in tool_names
        else:
            assert tool_name not in tool_names
