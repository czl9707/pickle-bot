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
    RouteCommand,
    BindingsCommand,
)
from picklebot.core.commands.registry import CommandRegistry
from picklebot.utils.def_loader import DefNotFoundError
from picklebot.core.agent_loader import AgentDef
from picklebot.utils.config import LLMConfig

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
            (SkillsCommand, "skills", [], "List all skills or show skill details"),
            (CronsCommand, "crons", [], "List all cron jobs or show cron details"),
            (CompactCommand, "compact", [], "Compact conversation context manually"),
            (ContextCommand, "context", [], "Show session context information"),
            (ClearCommand, "clear", [], "Clear conversation and start fresh"),
            (SessionCommand, "session", [], "Show current session details"),
            (
                RouteCommand,
                "route",
                [],
                "Create a routing binding (persists to config)",
            ),
            (BindingsCommand, "bindings", [], "Show all routing bindings"),
        ],
    )
    @pytest.mark.anyio
    async def test_command_properties(self, cls, name, aliases, description):
        """Command should have correct properties."""
        cmd = cls()
        assert cmd.name == name
        assert cmd.aliases == aliases
        assert cmd.description == description


class TestCommandExecute:
    """Tests for command execute behavior."""

    @pytest.mark.anyio
    async def test_help_command_with_session(self, mock_session):
        """Test help command with session context."""

        registry = CommandRegistry.with_builtins()
        mock_session.shared_context.command_registry = registry

        cmd = HelpCommand()
        result = await cmd.execute("", mock_session)
        assert "**Available Commands:**" in result


    @pytest.mark.anyio
    async def test_agent_command_list_with_session(self, mock_session, mock_context):
        """Test agent command lists agents."""
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
        result = await cmd.execute("", mock_session)
        assert "**Agents:**" in result
        assert "current-agent" in result
        assert "other-agent" in result

    @pytest.mark.anyio
    async def test_agent_no_agents(self, mock_session, mock_context):
        """AgentCommand with no agents should show empty list."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.discover_agents.return_value = []

        result = await AgentCommand().execute("", mock_session)
        assert "**Agents:**" in result

    @pytest.mark.anyio
    async def test_skills_no_skills(self, mock_session, mock_context):
        """SkillsCommand with no skills should show message."""
        mock_session.shared_context = mock_context
        mock_context.skill_loader.discover_skills.return_value = []

        result = await SkillsCommand().execute("", mock_session)
        assert "No skills configured" in result

    @pytest.mark.anyio
    async def test_skills_show_detail(self, mock_session, mock_context):
        """Test skills command shows detail for specific skill."""
        from picklebot.core.skill_loader import SkillDef

        mock_skill = SkillDef(
            id="brainstorm",
            name="Brainstorming",
            description="Turn ideas into designs",
            content="## How to brainstorm\n\nFollow these steps...",
        )
        mock_session.shared_context = mock_context
        mock_context.skill_loader.load_skill.return_value = mock_skill

        cmd = SkillsCommand()
        result = await cmd.execute("brainstorm", mock_session)

        assert "**Skill:** `brainstorm`" in result
        assert "**Name:** Brainstorming" in result
        assert "**Description:** Turn ideas into designs" in result
        assert "## How to brainstorm" in result
        mock_context.skill_loader.load_skill.assert_called_once_with("brainstorm")

    @pytest.mark.anyio
    async def test_skills_show_detail_not_found(self, mock_session, mock_context):
        """Test skills command handles non-existent skill."""
        from picklebot.utils.def_loader import DefNotFoundError

        mock_session.shared_context = mock_context
        mock_context.skill_loader.load_skill.side_effect = DefNotFoundError(
            "skill", "nonexistent"
        )

        cmd = SkillsCommand()
        result = await cmd.execute("nonexistent", mock_session)

        assert "not found" in result

    @pytest.mark.anyio
    async def test_crons_no_crons(self, mock_session, mock_context):
        """CronsCommand with no crons should show message."""
        mock_session.shared_context = mock_context
        mock_context.cron_loader.discover_crons.return_value = []

        result = await CronsCommand().execute("", mock_session)
        assert "No cron jobs configured" in result

    @pytest.mark.anyio
    async def test_crons_show_detail(self, mock_session, mock_context):
        """Test crons command shows detail for specific cron."""
        from picklebot.core.cron_loader import CronDef

        mock_cron = CronDef(
            id="daily-summary",
            name="Daily Summary",
            description="Daily summary cron",
            schedule="0 9 * * *",
            agent="pickle",
            prompt="Generate a daily summary of activities.",
        )
        mock_session.shared_context = mock_context
        mock_context.cron_loader.load.return_value = mock_cron

        cmd = CronsCommand()
        result = await cmd.execute("daily-summary", mock_session)

        assert "**Cron:** `daily-summary`" in result
        assert "**Name:** Daily Summary" in result
        assert "**Schedule:** `0 9 * * *`" in result
        assert "**Agent:** pickle" in result
        assert "Generate a daily summary" in result
        mock_context.cron_loader.load.assert_called_once_with("daily-summary")

    @pytest.mark.anyio
    async def test_crons_show_detail_not_found(self, mock_session, mock_context):
        """Test crons command handles non-existent cron."""
        mock_session.shared_context = mock_context
        mock_context.cron_loader.load.side_effect = DefNotFoundError(
            "cron", "nonexistent"
        )

        cmd = CronsCommand()
        result = await cmd.execute("nonexistent", mock_session)

        assert "not found" in result

    @pytest.mark.anyio
    async def test_agent_show_detail(self, mock_session, mock_context):
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
        result = await cmd.execute("current-agent", mock_session)

        assert "**Agent:** `current-agent`" in result
        assert "**Name:** Current Agent" in result
        assert "**Description:** Current agent desc" in result
        assert "**LLM:** test-model" in result
        assert "**AGENT.md:**" in result
        assert "You are current." in result
        assert "**SOUL.md:**" in result
        assert "Be friendly." in result
        mock_context.agent_loader.load.assert_called_once_with("current-agent")

    @pytest.mark.anyio
    async def test_agent_show_detail_not_found(self, mock_session, mock_context):
        """Test agent command handles non-existent agent."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.side_effect = ValueError("not found")

        cmd = AgentCommand()
        result = await cmd.execute("nonexistent", mock_session)

        assert "not found" in result

    @pytest.mark.anyio
    async def test_agent_show_detail_without_soul(self, mock_session, mock_context):
        """Test agent command shows detail without SOUL.md section."""
        from picklebot.core.agent_loader import AgentDef
        from picklebot.utils.config import LLMConfig

        llm_config = LLMConfig(provider="test", model="test-model", api_key="test-key")
        mock_agent = MagicMock()
        mock_agent.agent_def = AgentDef(
            id="no-soul-agent",
            name="No Soul Agent",
            description="An agent without SOUL.md",
            agent_md="You are an agent.",
            soul_md="",  # Empty - no SOUL.md
            llm=llm_config,
        )
        mock_session.agent = mock_agent
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.return_value = mock_agent.agent_def

        cmd = AgentCommand()
        result = await cmd.execute("no-soul-agent", mock_session)

        assert "**Agent:** `no-soul-agent`" in result
        assert "**AGENT.md:**" in result
        assert "**SOUL.md:**" not in result  # Should NOT appear when empty

    @pytest.mark.asyncio
    async def test_compact_command(self, mock_session):
        """Test compact command triggers compaction."""
        mock_session.context_guard.compact_and_roll = AsyncMock(
            return_value=mock_session.state
        )
        mock_session.context_guard.estimate_tokens = MagicMock(return_value=1000)

        cmd = CompactCommand()
        result = await cmd.execute("", mock_session)

        assert "✓ Context compacted" in result
        assert "messages retained" in result
        mock_session.context_guard.compact_and_roll.assert_called_once_with(
            mock_session.state
        )

    @pytest.mark.anyio
    async def test_context_command(self, mock_session):
        """Test context command shows session info."""
        mock_session.context_guard.estimate_tokens = MagicMock(return_value=1000)

        cmd = ContextCommand()
        result = await cmd.execute("", mock_session)

        assert "**Session:**" in result
        assert "**Agent:**" in result
        assert "**Messages:**" in result
        assert "**Tokens:**" in result

    @pytest.mark.anyio
    async def test_clear_command(self, mock_session, mock_context):
        """Test clear command clears session cache."""
        mock_session.shared_context = mock_context
        mock_session.source = MagicMock()
        mock_session.source.__str__ = MagicMock(return_value="platform-cli:test")

        cmd = ClearCommand()
        result = await cmd.execute("", mock_session)

        assert "✓ Conversation cleared" in result
        mock_context.routing_table.clear_session_cache.assert_called_once_with(
            "platform-cli:test"
        )

    @pytest.mark.anyio
    async def test_session_command(self, mock_session, mock_context):
        """Test session command shows session details."""
        mock_session.shared_context = mock_context
        mock_info = MagicMock()
        mock_info.created_at = "2024-01-01 12:00:00"
        mock_context.history_store.get_session_info.return_value = mock_info

        cmd = SessionCommand()
        result = await cmd.execute("", mock_session)

        assert "**Session ID:**" in result
        assert "**Agent:**" in result
        assert "**Created:**" in result
        assert "**Messages:**" in result
        assert "**Source:**" in result


class TestRouteCommand:
    """Tests for RouteCommand."""

    @pytest.mark.anyio
    async def test_route_creates_binding(self, mock_session, mock_context):
        """Test route command creates a binding."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.return_value = MagicMock()
        mock_context.config.routing = {"bindings": []}
        mock_context.config.sources = {}

        cmd = RouteCommand()
        result = await cmd.execute("platform-telegram:.* pickle", mock_session)

        assert "✓ Route bound" in result
        assert "platform-telegram:.*" in result
        assert "pickle" in result
        mock_context.routing_table.persist_binding.assert_called_once_with(
            "platform-telegram:.*", "pickle"
        )

    @pytest.mark.anyio
    async def test_route_missing_args(self, mock_session, mock_context):
        """Test route command with missing args."""
        mock_session.shared_context = mock_context

        cmd = RouteCommand()
        result = await cmd.execute("", mock_session)

        assert "Usage:" in result

    @pytest.mark.anyio
    async def test_route_agent_not_found(self, mock_session, mock_context):
        """Test route command with invalid agent."""
        mock_session.shared_context = mock_context
        mock_context.agent_loader.load.side_effect = ValueError("not found")

        cmd = RouteCommand()
        result = await cmd.execute("platform-telegram:.* nonexistent", mock_session)

        assert "not found" in result

    @pytest.mark.anyio
    async def test_route_invalid_regex(self, mock_session, mock_context):
        """Test route command with invalid regex pattern."""
        mock_session.shared_context = mock_context

        cmd = RouteCommand()
        result = await cmd.execute("[invalid pickle", mock_session)

        assert "Invalid regex pattern" in result


class TestBindingsCommand:
    """Tests for BindingsCommand."""

    @pytest.mark.anyio
    async def test_bindings_shows_all(self, mock_session, mock_context):
        """Test bindings command shows all bindings."""
        mock_session.shared_context = mock_context
        mock_context.config.routing = {
            "bindings": [
                {"agent": "pickle", "value": "platform-telegram:.*"},
                {"agent": "cookie", "value": "platform-discord:.*"},
            ]
        }

        cmd = BindingsCommand()
        result = await cmd.execute("", mock_session)

        assert "**Routing Bindings:**" in result
        assert "platform-telegram:.*" in result
        assert "pickle" in result
        assert "platform-discord:.*" in result
        assert "cookie" in result

    @pytest.mark.anyio
    async def test_bindings_empty(self, mock_session, mock_context):
        """Test bindings command with no bindings."""
        mock_session.shared_context = mock_context
        mock_context.config.routing = {"bindings": []}

        cmd = BindingsCommand()
        result = await cmd.execute("", mock_session)

        assert "No routing bindings configured" in result
