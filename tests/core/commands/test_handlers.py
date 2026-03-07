# tests/core/commands/test_handlers.py
"""Tests for built-in command handlers."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from picklebot.core.commands.handlers import (
    HelpCommand,
    AgentCommand,
    SkillsCommand,
    CronsCommand,
    CompactCommand,
    ContextCommand,
    ClearCommand,
    SessionCommand,
)


@pytest.fixture
def mock_session():
    """Create a mock AgentSession for testing with all required properties."""
    session = MagicMock()
    session.session_id = "session-123"
    session.shared_context = MagicMock()
    session.source = MagicMock()
    return session


@pytest.fixture
def mock_context():
    """Create a mock SharedContext for testing."""
    return MagicMock()


class TestCommandProperties:
    """Tests for command properties."""

    @pytest.mark.parametrize(
        "cls,name,aliases,description",
        [
            (HelpCommand, "help", ["?"], "Show available commands"),
            (
                AgentCommand,
                "agent",
                ["agents"],
                "List agents or show agent details",
            ),
            (SkillsCommand, "skills", [], "List all skills"),
            (CronsCommand, "crons", [], "List all cron jobs"),
            (CompactCommand, "compact", [], "Compact conversation context manually"),
            (ContextCommand, "context", [], "Show session context information"),
            (ClearCommand, "clear", [], "Clear conversation and start fresh"),
            (SessionCommand, "session", [], "Show current session details"),
        ],
    )
    def test_command_properties(self, cls, name, aliases, description):
        """Command should have correct properties."""
        cmd = cls()
        assert cmd.name == name
        assert cmd.aliases == aliases
        assert cmd.description == description


class TestCommandExecute:
    """Tests for command execute behavior."""

    def test_help_command_with_session(self, mock_session):
        """Test help command with session context."""
        from picklebot.core.commands.registry import CommandRegistry

        registry = CommandRegistry.with_builtins()
        mock_session.shared_context.command_registry = registry

        cmd = HelpCommand()
        result = cmd.execute("", mock_session)
        assert "**Available Commands:**" in result

    def test_agent_command_list_with_session(self, mock_session, mock_context):
        """Test agent command lists agents."""
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        # Create a proper LLMConfig
        llm_config = LLMConfig(provider="test", model="test-model", api_key="test-key")

        # Create a mock agent
        mock_agent = MagicMock()
        mock_agent.agent_def = AgentDef(
            id="current-agent",
            name="Current Agent",
            description="Current",
            agent_md="You are current.",
            llm=llm_config,
        )
        mock_session.agent = mock_agent

        # Mock the agent loader to return some agents
        mock_agents = [
            AgentDef(
                id="current-agent",
                name="Current Agent",
                description="Current",
                agent_md="You are current.",
                llm=llm_config,
            ),
            AgentDef(
                id="other-agent",
                name="Other Agent",
                description="Other",
                agent_md="You are other.",
                llm=llm_config,
            ),
        ]
        mock_session.shared_context = mock_context
        mock_context.agent_loader.discover_agents.return_value = mock_agents

        cmd = AgentCommand()
        result = cmd.execute("", mock_session)
        assert "**Agents:**" in result
        assert "current-agent" in result
        assert "other-agent" in result

    def test_agent_no_agents(self, mock_session, mock_context):
        """AgentCommand with no agents should show empty list."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.discover_agents.return_value = []

        result = AgentCommand().execute("", mock_session)
        assert "**Agents:**" in result

    def test_skills_no_skills(self, mock_session, mock_context):
        """SkillsCommand with no skills should show message."""
        mock_session.shared_context = mock_context
        mock_context.skill_loader.discover_skills.return_value = []

        result = SkillsCommand().execute("", mock_session)
        assert "No skills configured" in result

    def test_crons_no_crons(self, mock_session, mock_context):
        """CronsCommand with no crons should show message."""
        mock_session.shared_context = mock_context
        mock_context.cron_loader.discover_crons.return_value = []

        result = CronsCommand().execute("", mock_session)
        assert "No cron jobs configured" in result

    def test_agent_show_detail(self, mock_session, mock_context):
        """Test agent command shows detail for specific agent."""
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        llm_config = LLMConfig(provider="test", model="test-model", api_key="test-key")
        mock_agent = MagicMock()
        mock_agent.agent_def = AgentDef(
            id="current-agent",
            name="Current Agent",
            description="Current agent desc",
            agent_md="You are current.",
            soul_md="Be friendly.",
            llm=llm_config,
        )
        mock_session.agent = mock_agent
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.return_value = mock_agent.agent_def

        cmd = AgentCommand()
        result = cmd.execute("current-agent", mock_session)

        assert "**Agent:** `current-agent`" in result
        assert "**Name:** Current Agent" in result
        assert "**Description:** Current agent desc" in result
        mock_context.agent_loader.load.assert_called_once_with("current-agent")

    def test_agent_show_detail_not_found(self, mock_session, mock_context):
        """Test agent command handles non-existent agent."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.side_effect = ValueError("not found")

        cmd = AgentCommand()
        result = cmd.execute("nonexistent", mock_session)

        assert "not found" in result

    @pytest.mark.asyncio
    async def test_compact_command(self, mock_session):
        """Test compact command triggers compaction."""
        mock_session.context_guard.check_and_compact = AsyncMock(
            return_value=mock_session.state
        )
        mock_session.context_guard.estimate_tokens = MagicMock(return_value=1000)

        cmd = CompactCommand()
        result = await cmd.execute("", mock_session)

        assert "✓ Context compacted" in result
        assert "messages retained" in result
        mock_session.context_guard.check_and_compact.assert_called_once_with(
            mock_session.state, force=True
        )

    def test_context_command(self, mock_session):
        """Test context command shows session info."""
        mock_session.context_guard.estimate_tokens = MagicMock(return_value=1000)

        cmd = ContextCommand()
        result = cmd.execute("", mock_session)

        assert "**Session:**" in result
        assert "**Agent:**" in result
        assert "**Messages:**" in result
        assert "**Tokens:**" in result

    def test_clear_command(self, mock_session, mock_context):
        """Test clear command clears session cache."""
        mock_session.shared_context = mock_context
        mock_session.source = MagicMock()
        mock_session.source.__str__ = MagicMock(return_value="platform-cli:test")

        cmd = ClearCommand()
        result = cmd.execute("", mock_session)

        assert "✓ Conversation cleared" in result
        mock_context.routing_table.clear_session_cache.assert_called_once_with(
            "platform-cli:test"
        )

    def test_session_command(self, mock_session, mock_context):
        """Test session command shows session details."""
        mock_session.shared_context = mock_context
        mock_info = MagicMock()
        mock_info.created_at = "2024-01-01 12:00:00"
        mock_context.history_store.get_session_info.return_value = mock_info

        cmd = SessionCommand()
        result = cmd.execute("", mock_session)

        assert "**Session ID:**" in result
        assert "**Agent:**" in result
        assert "**Created:**" in result
        assert "**Messages:**" in result
        assert "**Source:**" in result
