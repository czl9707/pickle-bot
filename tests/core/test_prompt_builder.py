"""Tests for PromptBuilder."""

import pytest
from unittest.mock import MagicMock

from picklebot.core.prompt_builder import PromptBuilder
from picklebot.core.agent_loader import AgentDef
from picklebot.core.events import CronEventSource
from picklebot.messagebus.telegram_bus import TelegramEventSource
from picklebot.utils.config import LLMConfig


@pytest.fixture
def prompt_builder(tmp_path):
    """Create a PromptBuilder with temp workspace."""
    mock_cron_loader = MagicMock()
    mock_cron_loader.discover_crons.return_value = []
    return PromptBuilder(workspace_path=tmp_path, cron_loader=mock_cron_loader)


@pytest.fixture
def agent_def():
    """Create a test AgentDef."""
    return AgentDef(
        id="test-agent",
        name="Test Agent",
        agent_md="You are a test agent.",
        soul_md="Be friendly and helpful.",
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
    )


class TestPromptBuilderBasic:
    """Tests for basic prompt building."""

    def test_build_includes_agent_md(self, prompt_builder, agent_def):
        """Prompt should include agent_md."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are a test agent." in prompt

    def test_build_includes_soul_md(self, prompt_builder, agent_def):
        """Prompt should include soul_md if present."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Be friendly and helpful." in prompt

    def test_build_without_soul_md(self, prompt_builder):
        """Prompt should work without soul_md."""
        agent_def_no_soul = AgentDef(
            id="test-agent",
            name="Test Agent",
            agent_md="You are a test agent.",
            soul_md="",  # Empty
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
        )
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def_no_soul
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are a test agent." in prompt
        assert "Personality" not in prompt


class TestPromptBuilderRuntime:
    """Tests for runtime context layer."""

    def test_build_includes_agent_id(self, prompt_builder, agent_def):
        """Prompt should include agent ID."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "test-agent" in prompt

    def test_build_includes_timestamp(self, prompt_builder, agent_def):
        """Prompt should include timestamp."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Time:" in prompt


class TestPromptBuilderChannel:
    """Tests for channel hints layer."""

    def test_build_telegram_hint(self, prompt_builder, agent_def):
        """Prompt should include Telegram hint."""
        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are responding via telegram." in prompt

    def test_build_cron_hint(self, prompt_builder, agent_def):
        """Prompt should include cron hint."""
        source = CronEventSource(cron_id="daily-job")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "You are responding via cron" in prompt


class TestPromptBuilderBootstrap:
    """Tests for bootstrap context layer."""

    def test_build_includes_bootstrap_md(self, prompt_builder, agent_def, tmp_path):
        """Prompt should include BOOTSTRAP.md content."""
        bootstrap_md = tmp_path / "BOOTSTRAP.md"
        bootstrap_md.write_text("Workspace guidelines here.")

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Workspace guidelines here." in prompt

    def test_build_includes_agents_md(self, prompt_builder, agent_def, tmp_path):
        """Prompt should include AGENTS.md content."""
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("Available agents: cookie, pickle.")

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = prompt_builder.build(session)

        assert "Available agents: cookie, pickle." in prompt

    def test_build_includes_cron_list(self, agent_def, tmp_path):
        """Prompt should include cron list."""
        from picklebot.core.cron_loader import CronDef

        mock_cron = CronDef(
            id="daily",
            name="Daily Summary",
            description="Sends daily summary",
            agent="pickle",
            schedule="0 9 * * *",
            prompt="Summarize today.",
        )
        mock_cron_loader = MagicMock()
        mock_cron_loader.discover_crons.return_value = [mock_cron]

        builder = PromptBuilder(workspace_path=tmp_path, cron_loader=mock_cron_loader)

        source = TelegramEventSource(user_id="123", chat_id="456")
        session = MagicMock()
        session.agent.agent_def = agent_def
        session.source = source

        prompt = builder.build(session)

        assert "Daily Summary" in prompt
        assert "Sends daily summary" in prompt


class TestPromptBuilderIntegration:
    """Tests for SharedContext integration."""

    def test_shared_context_has_prompt_builder(self, test_config):
        """SharedContext should have prompt_builder."""
        from picklebot.core.context import SharedContext

        context = SharedContext(config=test_config)
        assert hasattr(context, "prompt_builder")
        assert context.prompt_builder is not None

    def test_prompt_builder_uses_context_paths(self, test_config, tmp_path):
        """PromptBuilder should use workspace path from context."""
        from picklebot.core.context import SharedContext

        context = SharedContext(config=test_config)
        assert context.prompt_builder.workspace_path == tmp_path
