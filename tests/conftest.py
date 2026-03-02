"""Shared test fixtures for picklebot test suite."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryStore
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
    )


@pytest.fixture
def test_agent(test_context: SharedContext, test_agent_def: AgentDef) -> Agent:
    """Agent instance for testing."""
    return Agent(agent_def=test_agent_def, context=test_context)


@pytest.fixture
def shared_llm() -> LLMConfig:
    """Shared LLM config for loader tests."""
    return LLMConfig(provider="test", model="test-model", api_key="test-key")


@pytest.fixture
def temp_agents_dir(tmp_path: Path) -> Path:
    """Temporary agents directory."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True)
    return agents_dir


@pytest.fixture
def temp_crons_dir(tmp_path: Path) -> Path:
    """Temporary crons directory."""
    crons_dir = tmp_path / "crons"
    crons_dir.mkdir(parents=True)
    return crons_dir


@pytest.fixture
def history_store(tmp_path: Path) -> HistoryStore:
    """HistoryStore instance for testing."""
    return HistoryStore(tmp_path / "history", max_history_file_size=3)


@pytest.fixture
def mock_context(tmp_path: Path) -> MagicMock:
    """Mock SharedContext for worker tests (no real agent loading)."""
    from picklebot.core.eventbus import EventBus

    context = MagicMock()
    context.config = MagicMock()
    context.config.messagebus = MagicMock()
    context.config.messagebus.telegram = None
    context.config.messagebus.discord = None
    context.config.event_path = tmp_path / ".events"
    context.eventbus = EventBus(context)
    context.messagebus_buses = []
    context.history_store = MagicMock()
    context.history_store.list_sessions = MagicMock(return_value=[])
    return context
