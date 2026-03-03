"""Tests for the Agent class."""

import pytest

from picklebot.core.agent import Agent, get_source_settings
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.core.events import AgentEventSource, CronEventSource
from picklebot.messagebus.telegram_bus import TelegramEventSource
from picklebot.messagebus.discord_bus import DiscordEventSource
from picklebot.messagebus.cli_bus import CliEventSource
from picklebot.utils.config import LLMConfig, MessageBusConfig, TelegramConfig


class TestGetSourceSettings:
    """Tests for source-based settings derivation."""

    def test_cron_source_returns_job_settings(self):
        """Cron sources should return job settings."""
        source = CronEventSource(cron_id="daily_summary")
        max_history, post_message = get_source_settings(source)
        assert max_history == 50
        assert post_message is True

    def test_cron_source_with_complex_id(self):
        """Cron sources with complex IDs should return job settings."""
        source = CronEventSource(cron_id="my-cron-job-123")
        max_history, post_message = get_source_settings(source)
        assert max_history == 50
        assert post_message is True

    def test_telegram_source_returns_chat_settings(self):
        """Telegram sources should return chat settings."""
        source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
        max_history, post_message = get_source_settings(source)
        assert max_history == 100
        assert post_message is False

    def test_discord_source_returns_chat_settings(self):
        """Discord sources should return chat settings."""
        source = DiscordEventSource(user_id="member_456", channel_id="channel_789")
        max_history, post_message = get_source_settings(source)
        assert max_history == 100
        assert post_message is False

    def test_agent_source_returns_chat_settings(self):
        """Agent (subagent) sources should return chat settings."""
        source = AgentEventSource(agent_id="cookie")
        max_history, post_message = get_source_settings(source)
        assert max_history == 100
        assert post_message is False

    def test_cli_source_returns_chat_settings(self):
        """CLI sources should return chat settings."""
        source = CliEventSource()
        max_history, post_message = get_source_settings(source)
        assert max_history == 100
        assert post_message is False


def test_agent_creation_with_new_structure(test_agent, test_agent_def, test_context):
    """Agent should be created with agent_def, llm, tools, context."""
    assert test_agent.agent_def is test_agent_def
    assert test_agent.context is test_context


def test_agent_new_session(test_agent, test_agent_def):
    """Agent should create new session with self reference and correct source defaults."""
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = test_agent.new_session(source=source)

    assert session.session_id is not None
    assert session.agent_id == test_agent_def.id
    assert session.agent is test_agent
    assert session.max_history == 100  # chat default from get_source_settings


def test_agent_new_session_with_custom_session_id(test_agent):
    """Agent.new_session should accept optional session_id parameter."""
    custom_id = "custom-session-123"
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = test_agent.new_session(source=source, session_id=custom_id)

    assert session.session_id == custom_id


@pytest.mark.parametrize(
    "source,expected_max_history",
    [
        (
            TelegramEventSource(user_id="user_123", chat_id="chat_456"),
            100,
        ),  # chat source -> 100
        (CronEventSource(cron_id="daily_job"), 50),  # cron source -> 50
    ],
)
def test_session_max_history(test_agent, source, expected_max_history):
    """Agent.new_session should use correct max_history based on source."""
    session = test_agent.new_session(source)
    assert session.max_history == expected_max_history


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
        agent_md="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
        allow_skills=allow_skills,
    )
    context = SharedContext(config=test_config)
    return Agent(agent_def=agent_def, context=context)


@pytest.mark.parametrize(
    "allow_skills,expected",
    [
        (True, True),
        (False, False),
    ],
)
def test_skill_tool_registration(test_config, allow_skills, expected):
    """Session should register skill tool based on allow_skills setting."""
    agent = _create_agent_with_skills(test_config, allow_skills)
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = agent.new_session(source=source)
    tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]

    assert ("skill" in tool_names) == expected


def _create_agent_with_other_agents(
    test_config, test_agent_def, has_other_agents: bool
) -> Agent:
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


@pytest.mark.parametrize(
    "has_other_agents,expected",
    [
        (True, True),
        (False, False),
    ],
)
def test_subagent_dispatch_registration(
    test_config, test_agent_def, has_other_agents, expected
):
    """Session should register subagent_dispatch tool only when other agents exist."""
    agent = _create_agent_with_other_agents(
        test_config, test_agent_def, has_other_agents
    )
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = agent.new_session(source=source)
    tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]

    assert ("subagent_dispatch" in tool_names) == expected


def _create_agent_with_messagebus(test_config) -> Agent:
    """Helper to create an agent with messagebus enabled."""
    test_config.messagebus = MessageBusConfig(
        enabled=True,
        telegram=TelegramConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["123"],
        ),
    )

    agent_def = AgentDef(
        id="test-agent",
        name="Test Agent",
        agent_md="You are a test assistant.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
    )
    context = SharedContext(config=test_config)
    return Agent(agent_def=agent_def, context=context)


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            TelegramEventSource(user_id="user_123", chat_id="chat_456"),
            False,
        ),  # chat source -> no post_message
        (CronEventSource(cron_id="daily_job"), True),  # cron source -> post_message
    ],
)
def test_post_message_availability(test_config, source, expected):
    """post_message tool should only be available for cron sources."""
    agent = _create_agent_with_messagebus(test_config)
    session = agent.new_session(source=source)
    tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]

    assert ("post_message" in tool_names) == expected


class TestAgentNewSessionWithSource:
    """Tests for Agent.new_session with source parameter."""

    @pytest.fixture
    def mock_context(self, tmp_path):
        """Create a mock SharedContext for testing."""
        from unittest.mock import MagicMock
        from picklebot.core.history import HistoryStore

        context = MagicMock()
        context.config.chat_max_history = 100
        context.config.job_max_history = 50
        context.config.messagebus = MagicMock()
        context.config.messagebus.enabled = True
        context.config.messagebus.telegram = MagicMock()
        context.config.messagebus.telegram.enabled = True
        context.config.websearch = None
        context.config.webread = None
        context.history_store = HistoryStore(tmp_path)
        context.skill_loader = MagicMock()
        context.skill_loader.list_skills.return_value = []
        # Mock messagebus_buses for post_message_tool
        mock_bus = MagicMock()
        mock_bus.platform_name = "telegram"
        context.messagebus_buses = [mock_bus]

        return context

    @pytest.fixture
    def mock_agent_def(self):
        """Create a mock AgentDef for testing."""
        from unittest.mock import MagicMock

        agent_def = MagicMock()
        agent_def.id = "test-agent"
        agent_def.llm = LLMConfig(provider="openai", model="gpt-4", api_key="test-key")
        agent_def.agent_md = "You are a test agent."
        agent_def.allow_skills = False
        agent_def.max_concurrency = 1
        return agent_def

    def test_new_session_accepts_source(self, mock_context, mock_agent_def):
        """new_session should accept source parameter."""
        agent = Agent(mock_agent_def, mock_context)
        source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
        session = agent.new_session(source=source)

        assert session.source == source

    def test_new_session_context_from_source(self, mock_context, mock_agent_def):
        """new_session should accept CliEventSource object."""
        source = CliEventSource()

        agent = Agent(mock_agent_def, mock_context)
        session = agent.new_session(source=source)

        assert session.source == source

    def test_new_session_derives_max_history_from_source_cron(
        self, mock_context, mock_agent_def
    ):
        """new_session should derive max_history from source for cron."""
        agent = Agent(mock_agent_def, mock_context)
        source = CronEventSource(cron_id="daily_job")
        session = agent.new_session(source=source)

        assert session.max_history == 50

    def test_new_session_derives_max_history_from_source_chat(
        self, mock_context, mock_agent_def
    ):
        """new_session should derive max_history from source for chat."""
        agent = Agent(mock_agent_def, mock_context)
        source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
        session = agent.new_session(source=source)

        assert session.max_history == 100

    def test_new_session_includes_post_message_for_cron(
        self, mock_context, mock_agent_def
    ):
        """new_session should include post_message tool for cron sources."""
        agent = Agent(mock_agent_def, mock_context)
        source = CronEventSource(cron_id="daily_job")
        session = agent.new_session(source=source)

        tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]
        assert "post_message" in tool_names

    def test_new_session_excludes_post_message_for_chat(
        self, mock_context, mock_agent_def
    ):
        """new_session should NOT include post_message tool for chat sources."""
        agent = Agent(mock_agent_def, mock_context)
        source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
        session = agent.new_session(source=source)

        tool_names = [s["function"]["name"] for s in session.tools.get_tool_schemas()]
        assert "post_message" not in tool_names

    def test_new_session_persists_source_to_history(self, mock_context, mock_agent_def):
        """new_session should persist source to HistoryStore."""
        agent = Agent(mock_agent_def, mock_context)
        source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
        session = agent.new_session(source=source)

        # Check that history store has the session with source
        sessions = mock_context.history_store.list_sessions()
        stored = next((s for s in sessions if s.id == session.session_id), None)
        assert stored is not None
        assert stored.source == str(source)


def test_session_builds_prompt_with_layers(test_agent):
    """AgentSession._build_messages should use PromptBuilder."""
    source = TelegramEventSource(user_id="123", chat_id="456")
    session = test_agent.new_session(source=source)

    messages = session._build_messages()
    system_prompt = messages[0]["content"]

    # Should include agent_md
    assert "You are a test assistant." in system_prompt
    # Should include channel hint
    assert "telegram" in system_prompt.lower()
    # Should include runtime
    assert "Agent:" in system_prompt
