"""Shared test fixtures for picklebot test suite."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

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
        agent_md="You are a test assistant.",  # Changed from system_prompt
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


@pytest.fixture
def api_client(tmp_path: Path):
    """TestClient with pre-configured workspace. Yields (client, workspace)."""
    from picklebot.api import create_app

    # Ensure directories exist
    (tmp_path / "agents").mkdir(exist_ok=True)
    (tmp_path / "skills").mkdir(exist_ok=True)
    (tmp_path / "crons").mkdir(exist_ok=True)

    config = Config(
        workspace=tmp_path,
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        default_agent="pickle",
    )
    context = SharedContext(config)
    app = create_app(context)

    with TestClient(app) as client:
        yield client, tmp_path


@pytest.fixture
def api_client_with_agent(api_client):
    """TestClient with a test agent already created."""
    from tests.helpers import create_test_agent

    client, workspace = api_client
    create_test_agent(workspace, agent_id="test-agent")
    return client, workspace


@pytest.fixture
def api_client_with_skill(api_client):
    """TestClient with a test skill already created."""
    from tests.helpers import create_test_skill

    client, workspace = api_client
    create_test_skill(workspace, skill_id="test-skill")
    return client, workspace


@pytest.fixture
def api_client_with_cron(api_client):
    """TestClient with a test cron already created."""
    from tests.helpers import create_test_cron

    client, workspace = api_client
    create_test_cron(workspace, cron_id="test-cron")
    return client, workspace
