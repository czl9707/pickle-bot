"""Shared test fixtures for picklebot test suite."""

from pathlib import Path

import pytest

from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentBehaviorConfig, AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def llm_config() -> LLMConfig:
    """Minimal LLM config for testing."""
    return LLMConfig(provider="openai", model="gpt-4", api_key="test-key")


@pytest.fixture
def test_config(tmp_path: Path, llm_config: LLMConfig) -> Config:
    """Config with workspace pointing to tmp_path."""
    return Config(workspace=tmp_path, llm=llm_config, default_agent="test")


@pytest.fixture
def test_context(test_config: Config) -> SharedContext:
    """SharedContext with test config."""
    return SharedContext(config=test_config)


@pytest.fixture
def test_agent_def(llm_config: LLMConfig) -> AgentDef:
    """Minimal AgentDef for testing."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        description="A test agent",
        system_prompt="You are a test assistant.",
        llm=llm_config,
        behavior=AgentBehaviorConfig(),
    )


@pytest.fixture
def test_agent(test_context: SharedContext, test_agent_def: AgentDef) -> Agent:
    """Agent instance for testing."""
    return Agent(agent_def=test_agent_def, context=test_context)
