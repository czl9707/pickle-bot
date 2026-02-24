# tests/cli/onboarding/test_steps.py
"""Unit tests for onboarding step classes."""

from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from picklebot.cli.onboarding.steps import (
    BaseStep,
    CheckWorkspaceStep,
    SetupWorkspaceStep,
    ConfigureLLMStep,
    ConfigureExtraFunctionalityStep,
    CopyDefaultAssetsStep,
    ConfigureMessageBusStep,
    SaveConfigStep,
)


class TestBaseStep:
    """Tests for BaseStep."""

    def test_init_stores_dependencies(self, tmp_path: Path):
        """BaseStep stores workspace, console, and defaults."""
        console = Console()
        defaults = tmp_path / "defaults"

        step = BaseStep(tmp_path, console, defaults)

        assert step.workspace == tmp_path
        assert step.console is console
        assert step.defaults == defaults

    def test_run_raises_not_implemented(self, tmp_path: Path):
        """BaseStep.run raises NotImplementedError."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = BaseStep(tmp_path, console, defaults)

        with pytest.raises(NotImplementedError):
            step.run({})


class TestSetupWorkspaceStep:
    """Tests for SetupWorkspaceStep."""

    def test_creates_all_directories(self, tmp_path: Path):
        """SetupWorkspaceStep creates all required directories."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        step = SetupWorkspaceStep(workspace, console, defaults)

        result = step.run({})

        assert result is True
        assert workspace.exists()
        assert (workspace / "agents").exists()
        assert (workspace / "skills").exists()
        assert (workspace / "crons").exists()
        assert (workspace / "memories").exists()
        assert (workspace / ".history").exists()
        assert (workspace / ".logs").exists()

    def test_idempotent(self, tmp_path: Path):
        """SetupWorkspaceStep can be run multiple times safely."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        step = SetupWorkspaceStep(workspace, console, defaults)

        step.run({})
        result = step.run({})

        assert result is True


class TestCheckWorkspaceStep:
    """Tests for CheckWorkspaceStep."""

    def test_returns_true_when_no_config(self, tmp_path: Path):
        """Returns True when config.user.yaml doesn't exist."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        step = CheckWorkspaceStep(workspace, console, defaults)

        result = step.run({})

        assert result is True

    def test_prompts_when_config_exists(self, tmp_path: Path):
        """Prompts user when config.user.yaml exists."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")
        step = CheckWorkspaceStep(workspace, console, defaults)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            result = step.run({})

        mock_confirm.assert_called_once()
        assert result is True

    def test_returns_false_when_user_declines(self, tmp_path: Path):
        """Returns False when user declines overwrite."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")
        step = CheckWorkspaceStep(workspace, console, defaults)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = step.run({})

        assert result is False


class TestConfigureLLMStep:
    """Tests for ConfigureLLMStep."""

    def test_stores_llm_config_in_state(self, tmp_path: Path):
        """ConfigureLLMStep stores LLM config in state."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureLLMStep(tmp_path, console, defaults)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
        ):
            mock_select.return_value.ask.return_value = "openai"
            mock_text.return_value.ask.side_effect = ["gpt-4o", "sk-test", ""]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["llm"]["provider"] == "openai"
        assert state["llm"]["model"] == "gpt-4o"
        assert state["llm"]["api_key"] == "sk-test"
        assert "api_base" not in state["llm"]

    def test_includes_api_base_when_provided(self, tmp_path: Path):
        """ConfigureLLMStep includes api_base when user provides one."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureLLMStep(tmp_path, console, defaults)

        with (
            patch("questionary.select") as mock_select,
            patch("questionary.text") as mock_text,
        ):
            mock_select.return_value.ask.return_value = "other"
            mock_text.return_value.ask.side_effect = [
                "llama-3",
                "my-key",
                "http://localhost:11434",
            ]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["llm"]["api_base"] == "http://localhost:11434"


class TestConfigureExtraFunctionalityStep:
    """Tests for ConfigureExtraFunctionalityStep."""

    def test_no_selection_no_state(self, tmp_path: Path):
        """No selection results in no state changes."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = []

            state = {}
            result = step.run(state)

        assert result is True
        assert "websearch" not in state
        assert "webread" not in state
        assert "api" not in state

    def test_websearch_with_api_key(self, tmp_path: Path):
        """Websearch selection with API key stores config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["websearch"]
            mock_text.return_value.ask.return_value = "test-api-key"

            state = {}
            result = step.run(state)

        assert result is True
        assert state["websearch"] == {"provider": "brave", "api_key": "test-api-key"}

    def test_websearch_empty_key_skips(self, tmp_path: Path, capsys):
        """Websearch with empty API key skips config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["websearch"]
            mock_text.return_value.ask.return_value = ""

            state = {}
            result = step.run(state)

        assert result is True
        assert "websearch" not in state

    def test_webread_selection(self, tmp_path: Path):
        """Webread selection stores config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = ["webread"]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["webread"] == {"provider": "crawl4ai"}

    def test_api_selection(self, tmp_path: Path):
        """API selection stores enabled config."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = ["api"]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["api"] == {"enabled": True}

    def test_all_selections(self, tmp_path: Path):
        """All features can be selected together."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureExtraFunctionalityStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = [
                "websearch",
                "webread",
                "api",
            ]
            mock_text.return_value.ask.return_value = "test-key"

            state = {}
            result = step.run(state)

        assert result is True
        assert "websearch" in state
        assert "webread" in state
        assert "api" in state


class TestCopyDefaultAssetsStep:
    """Tests for CopyDefaultAssetsStep."""

    def test_skips_when_no_defaults(self, tmp_path: Path):
        """Does nothing when defaults directory doesn't exist."""
        console = Console()
        defaults = tmp_path / "nonexistent"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()
        (workspace / "skills").mkdir()
        step = CopyDefaultAssetsStep(workspace, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            result = step.run({})

        mock_checkbox.assert_not_called()
        assert result is True

    def test_copies_selected_assets(self, tmp_path: Path):
        """Copies selected agents and skills to workspace."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()
        (workspace / "skills").mkdir()

        # Create mock default agent with valid frontmatter
        mock_agent = defaults / "agents" / "pickle"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text(
            "---\nname: Pickle\ndescription: Test agent\n---\n# Pickle Agent"
        )

        step = CopyDefaultAssetsStep(workspace, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.side_effect = [["pickle"], []]
            result = step.run({})

        assert result is True
        assert (workspace / "agents" / "pickle").exists()
        assert (
            "Pickle Agent" in (workspace / "agents" / "pickle" / "AGENT.md").read_text()
        )

    def test_overwrites_existing(self, tmp_path: Path):
        """Overwrites existing assets in workspace."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        agents_dir = workspace / "agents"
        agents_dir.mkdir()

        # Create existing asset with old content
        existing = agents_dir / "pickle"
        existing.mkdir()
        (existing / "AGENT.md").write_text("# Old Content")

        # Create default with new content
        mock_agent = defaults / "agents" / "pickle"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text(
            "---\nname: Pickle\ndescription: Test agent\n---\n# New Content"
        )

        step = CopyDefaultAssetsStep(workspace, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.side_effect = [["pickle"], []]
            result = step.run({})

        assert result is True
        assert (
            workspace / "agents" / "pickle" / "AGENT.md"
        ).read_text() == "---\nname: Pickle\ndescription: Test agent\n---\n# New Content"


class TestConfigureMessageBusStep:
    """Tests for ConfigureMessageBusStep."""

    def test_no_platforms_disables_messagebus(self, tmp_path: Path):
        """No platform selection disables messagebus."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureMessageBusStep(tmp_path, console, defaults)

        with patch("questionary.checkbox") as mock_checkbox:
            mock_checkbox.return_value.ask.return_value = []

            state = {}
            result = step.run(state)

        assert result is True
        assert state["messagebus"]["enabled"] is False

    def test_telegram_configuration(self, tmp_path: Path):
        """Telegram selection prompts for token and users."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureMessageBusStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["telegram"]
            mock_text.return_value.ask.side_effect = [
                "123:ABC",  # bot token
                "12345",  # allowed users
                "12345",  # default chat
            ]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["messagebus"]["enabled"] is True
        assert state["messagebus"]["default_platform"] == "telegram"
        assert state["messagebus"]["telegram"]["bot_token"] == "123:ABC"

    def test_discord_configuration(self, tmp_path: Path):
        """Discord selection prompts for token and users."""
        console = Console()
        defaults = tmp_path / "defaults"
        step = ConfigureMessageBusStep(tmp_path, console, defaults)

        with (
            patch("questionary.checkbox") as mock_checkbox,
            patch("questionary.text") as mock_text,
        ):
            mock_checkbox.return_value.ask.return_value = ["discord"]
            mock_text.return_value.ask.side_effect = [
                "discord-token",  # bot token
                "",  # channel id (skip)
                "",  # allowed users (skip)
                "",  # default chat (skip)
            ]

            state = {}
            result = step.run(state)

        assert result is True
        assert state["messagebus"]["enabled"] is True
        assert state["messagebus"]["default_platform"] == "discord"
        assert state["messagebus"]["discord"]["bot_token"] == "discord-token"


class TestSaveConfigStep:
    """Tests for SaveConfigStep."""

    def test_writes_yaml_file(self, tmp_path: Path):
        """SaveConfigStep writes config.user.yaml."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        step = SaveConfigStep(workspace, console, defaults)

        state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }
        result = step.run(state)

        assert result is True
        config_path = workspace / "config.user.yaml"
        assert config_path.exists()

    def test_adds_default_agent(self, tmp_path: Path):
        """SaveConfigStep adds default_agent if not present."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        step = SaveConfigStep(workspace, console, defaults)

        state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }
        step.run(state)

        assert state["default_agent"] == "pickle"

    def test_validates_config(self, tmp_path: Path):
        """SaveConfigStep validates config with Pydantic."""
        console = Console()
        defaults = tmp_path / "defaults"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        step = SaveConfigStep(workspace, console, defaults)

        # Missing required fields
        state = {
            "llm": {"provider": "openai"},  # missing model and api_key
            "messagebus": {"enabled": False},
        }
        result = step.run(state)

        assert result is False
