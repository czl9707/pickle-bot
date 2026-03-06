"""Tests for the Agent class."""

import pytest

from picklebot.core.agent import Agent
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.core.events import CronEventSource, CliEventSource
from picklebot.channel.telegram_channel import TelegramEventSource
from picklebot.utils.config import LLMConfig, ChannelConfig, TelegramConfig


def test_agent_creation_with_new_structure(test_agent, test_agent_def, test_context):
    """Agent should be created with agent_def, llm, tools, context."""
    assert test_agent.agent_def is test_agent_def
    assert test_agent.context is test_context


def test_agent_new_session(test_agent, test_agent_def):
    """Agent should create new session with self reference and correct source."""
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = test_agent.new_session(source=source)

    assert session.session_id is not None
    assert session.agent is test_agent
    assert session.source == source


def test_agent_new_session_with_custom_session_id(test_agent):
    """Agent.new_session should accept optional session_id parameter."""
    custom_id = "custom-session-123"
    source = TelegramEventSource(user_id="user_123", chat_id="chat_456")
    session = test_agent.new_session(source=source, session_id=custom_id)

    assert session.session_id == custom_id


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
    test_config.channels = ChannelConfig(
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
        context.config.channels = MagicMock()
        context.config.channels.enabled = True
        context.config.channels.telegram = MagicMock()
        context.config.channels.telegram.enabled = True
        context.config.websearch = None
        context.config.webread = None
        context.history_store = HistoryStore(tmp_path)
        context.skill_loader = MagicMock()
        context.skill_loader.list_skills.return_value = []
        # Mock channels for post_message_tool
        mock_bus = MagicMock()
        mock_bus.platform_name = "telegram"
        context.channels = [mock_bus]

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

    messages = session.state.build_messages()
    system_prompt = messages[0]["content"]

    # Should include agent_md
    assert "You are a test assistant." in system_prompt
    # Should include channel hint
    assert "telegram" in system_prompt.lower()
    # Should include runtime
    assert "Agent:" in system_prompt


class TestAgentSessionWithSessionState:
    """Tests for AgentSession integration with SessionState."""

    def test_agent_session_has_state(self, test_agent):
        """AgentSession should have a state field."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = test_agent.new_session(source=source)
        assert hasattr(session, "state")
        assert session.state.session_id == session.session_id

    def test_agent_session_state_is_swappable(self, test_agent):
        """AgentSession.state should be swappable."""
        from picklebot.core.session_state import SessionState

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = test_agent.new_session(source=source)

        new_state = SessionState(
            session_id="new-session-id",
            agent=test_agent,
            messages=[],
            source=source,
            shared_context=test_agent.context,
        )

        session.state = new_state
        assert session.state.session_id == "new-session-id"

    def test_agent_session_delegates_properties_to_state(self, test_agent):
        """AgentSession properties should delegate to state."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = test_agent.new_session(source=source)

        # Properties should delegate to state
        assert session.session_id == session.state.session_id
        assert session.source == session.state.source
        assert session.shared_context == session.state.shared_context

    def test_agent_session_state_has_initial_messages(self, test_agent):
        """AgentSession.state should have empty messages initially."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = test_agent.new_session(source=source)

        assert hasattr(session.state, "messages")
        assert session.state.messages == []

    def test_agent_session_add_message_through_state(self, test_agent):
        """Messages are added directly to state."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = test_agent.new_session(source=source)

        # Add message directly to state
        user_msg = {"role": "user", "content": "test message"}
        session.state.add_message(user_msg)

        # Should be in state.messages
        assert user_msg in session.state.messages


class TestSessionRollingIntegration:
    """Integration tests for session rolling with SessionState."""

    @pytest.mark.asyncio
    async def test_messages_go_to_new_session_after_roll(self, test_agent):
        """After rolling, new messages should go to the new session."""
        from unittest.mock import AsyncMock, patch
        from picklebot.core.session_state import SessionState

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = test_agent.new_session(source=source)

        old_session_id = session.session_id

        # Create a new state that will be returned by check_and_compact
        new_state = SessionState(
            session_id="new-rolled-session",
            agent=test_agent,
            messages=[],
            source=source,
            shared_context=test_agent.context,
        )

        # Create the new session in history
        test_agent.context.history_store.create_session(
            test_agent.agent_def.id, "new-rolled-session", source
        )

        # Mock LLM to return response
        with patch.object(
            test_agent.llm,
            "chat",
            new_callable=AsyncMock,
            return_value=("Response", []),
        ):
            # Mock check_and_compact to trigger a roll
            with patch.object(
                session.context_guard,
                "check_and_compact",
                new_callable=AsyncMock,
                return_value=new_state,
            ):
                await session.chat("Hello")

        # State should be swapped
        assert session.state.session_id == "new-rolled-session"
        assert session.state.session_id != old_session_id

        # Assistant message should be in NEW session
        new_session_messages = test_agent.context.history_store.get_messages(
            "new-rolled-session"
        )
        assert len(new_session_messages) >= 1
        # The assistant response should be persisted to the new session
        assert any(m.role == "assistant" for m in new_session_messages)
