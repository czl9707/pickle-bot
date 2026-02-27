# tests/core/commands/test_handlers.py
"""Tests for built-in command handlers."""

from picklebot.core.commands.base import CommandResult
from picklebot.core.commands.handlers import (
    HelpCommand,
    AgentCommand,
    SkillsCommand,
    CronsCommand,
)


class TestHelpCommand:
    """Tests for HelpCommand."""

    def test_name(self):
        """HelpCommand name should be 'help'."""
        cmd = HelpCommand()
        assert cmd.name == "help"

    def test_aliases(self):
        """HelpCommand should have '?' alias."""
        cmd = HelpCommand()
        assert "?" in cmd.aliases

    def test_description(self):
        """HelpCommand should have description."""
        cmd = HelpCommand()
        assert cmd.description == "Show available commands"

    def test_execute_returns_available_commands(self):
        """execute() should list available commands."""
        from picklebot.core.commands.registry import CommandRegistry

        # Use with_builtins which sets registry on HelpCommand
        registry = CommandRegistry.with_builtins()
        result = registry.dispatch("/help", None)

        assert isinstance(result, CommandResult)
        assert "/help" in result.message
        assert "/agent" in result.message
        assert "/skills" in result.message
        assert "/crons" in result.message


class TestAgentCommand:
    """Tests for AgentCommand."""

    def test_name(self):
        """AgentCommand name should be 'agent'."""
        cmd = AgentCommand()
        assert cmd.name == "agent"

    def test_aliases(self):
        """AgentCommand should have 'agents' alias."""
        cmd = AgentCommand()
        assert "agents" in cmd.aliases

    def test_description(self):
        """AgentCommand should have description."""
        cmd = AgentCommand()
        assert cmd.description == "List all agents"

    def test_execute_no_agents(self, test_context):
        """execute() should show message when no agents configured."""
        cmd = AgentCommand()
        result = cmd.execute("", test_context)

        assert "No agents configured" in result.message

    def test_execute_with_agents(self, test_context, temp_agents_dir):
        """execute() should list agents."""
        # Create a test agent
        agent_dir = temp_agents_dir / "test-bot"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text(
            """---
name: Test Bot
---
You are a test bot.
"""
        )

        cmd = AgentCommand()
        result = cmd.execute("", test_context)

        assert "test-bot" in result.message
        assert "Test Bot" in result.message


class TestSkillsCommand:
    """Tests for SkillsCommand."""

    def test_name(self):
        """SkillsCommand name should be 'skills'."""
        cmd = SkillsCommand()
        assert cmd.name == "skills"

    def test_description(self):
        """SkillsCommand should have description."""
        cmd = SkillsCommand()
        assert cmd.description == "List all skills"

    def test_execute_no_skills(self, test_context):
        """execute() should show message when no skills configured."""
        cmd = SkillsCommand()
        result = cmd.execute("", test_context)

        assert "No skills configured" in result.message


class TestCronsCommand:
    """Tests for CronsCommand."""

    def test_name(self):
        """CronsCommand name should be 'crons'."""
        cmd = CronsCommand()
        assert cmd.name == "crons"

    def test_description(self):
        """CronsCommand should have description."""
        cmd = CronsCommand()
        assert cmd.description == "List all cron jobs"

    def test_execute_no_crons(self, test_context):
        """execute() should show message when no crons configured."""
        cmd = CronsCommand()
        result = cmd.execute("", test_context)

        assert "No cron jobs configured" in result.message
