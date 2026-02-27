# tests/core/commands/test_handlers.py
"""Tests for built-in command handlers."""

import pytest

from picklebot.core.commands.handlers import (
    HelpCommand,
    AgentCommand,
    SkillsCommand,
    CronsCommand,
)


class TestCommandProperties:
    """Tests for command properties."""

    @pytest.mark.parametrize(
        "cls,name,aliases,description",
        [
            (HelpCommand, "help", ["?"], "Show available commands"),
            (AgentCommand, "agent", ["agents"], "List all agents"),
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

    def test_help_lists_commands(self):
        """HelpCommand should list all commands."""
        from unittest.mock import MagicMock
        from picklebot.core.commands.registry import CommandRegistry

        registry = CommandRegistry.with_builtins()
        mock_ctx = MagicMock()
        mock_ctx.command_registry = registry
        result = registry.dispatch("/help", mock_ctx)

        assert "/help" in result
        assert "/agent" in result
        assert "/skills" in result
        assert "/crons" in result

    def test_agent_no_agents(self, test_context):
        """AgentCommand with no agents should show message."""
        result = AgentCommand().execute("", test_context)
        assert "No agents configured" in result

    def test_skills_no_skills(self, test_context):
        """SkillsCommand with no skills should show message."""
        result = SkillsCommand().execute("", test_context)
        assert "No skills configured" in result

    def test_crons_no_crons(self, test_context):
        """CronsCommand with no crons should show message."""
        result = CronsCommand().execute("", test_context)
        assert "No cron jobs configured" in result
