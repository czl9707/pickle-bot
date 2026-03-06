# tests/core/commands/test_handlers.py
"""Tests for built-in command handlers."""

import pytest
from unittest.mock import MagicMock

from picklebot.core.commands.handlers import (
    HelpCommand,
    AgentCommand,
    SkillsCommand,
    CronsCommand,
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
                "Switch to a different agent (starts fresh session)",
            ),
            (SkillsCommand, "skills", [], "List all skills"),
            (CronsCommand, "crons", [], "List all cron jobs"),
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
