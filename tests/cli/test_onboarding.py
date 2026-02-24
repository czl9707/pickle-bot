"""Tests for onboarding wizard."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

from picklebot.cli.onboarding import OnboardingWizard


def test_wizard_instantiates():
    """Test that OnboardingWizard can be instantiated."""
    wizard = OnboardingWizard()
    assert wizard.state == {}


def test_setup_workspace_creates_directories():
    """Test that setup_workspace creates all required directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)
        wizard.setup_workspace()

        assert workspace.exists()
        assert (workspace / "agents").exists()
        assert (workspace / "skills").exists()
        assert (workspace / "crons").exists()
        assert (workspace / "memories").exists()
        assert (workspace / ".history").exists()
        assert (workspace / ".logs").exists()


def test_configure_llm_stores_state():
    """Test that configure_llm stores LLM config in state."""
    wizard = OnboardingWizard()

    with (
        patch("questionary.select") as mock_select,
        patch("questionary.text") as mock_text,
    ):
        # Mock select returns the provider config_name
        mock_select.return_value.ask.return_value = "openai"
        # Model, api_key, then api_base (user presses enter to skip with empty default)
        mock_text.return_value.ask.side_effect = ["gpt-4o", "sk-test-key", ""]

        wizard.configure_llm()

    assert wizard.state["llm"]["provider"] == "openai"
    assert wizard.state["llm"]["model"] == "gpt-4o"  # default from provider
    assert wizard.state["llm"]["api_key"] == "sk-test-key"
    assert wizard.state["llm"].get("api_base") is None


def test_configure_llm_other_provider_prompts_api_base():
    """Test that other provider prompts for api_base."""
    wizard = OnboardingWizard()

    with (
        patch("questionary.select") as mock_select,
        patch("questionary.text") as mock_text,
    ):
        mock_select.return_value.ask.return_value = "other"
        mock_text.return_value.ask.side_effect = [
            "llama-3",  # model (no default)
            "my-key",  # api_key
            "http://localhost:11434",  # api_base
        ]

        wizard.configure_llm()

    assert wizard.state["llm"]["provider"] == "other"
    assert wizard.state["llm"]["model"] == "llama-3"
    assert wizard.state["llm"]["api_key"] == "my-key"
    assert wizard.state["llm"]["api_base"] == "http://localhost:11434"


def test_configure_messagebus_stores_state():
    """Test that configure_messagebus stores MessageBus config in state."""
    wizard = OnboardingWizard()

    with (
        patch("questionary.checkbox") as mock_checkbox,
        patch("questionary.text") as mock_text,
    ):
        # Select telegram only
        mock_checkbox.return_value.ask.return_value = ["telegram"]
        mock_text.return_value.ask.side_effect = [
            "123:ABC",  # telegram bot token
            "12345",  # telegram allowed user ids
            "12345",  # telegram default chat id
        ]

        wizard.configure_messagebus()

    assert wizard.state["messagebus"]["enabled"] is True
    assert wizard.state["messagebus"]["default_platform"] == "telegram"
    assert wizard.state["messagebus"]["telegram"]["bot_token"] == "123:ABC"


def test_configure_messagebus_skip_all():
    """Test that selecting no platforms results in disabled messagebus."""
    wizard = OnboardingWizard()

    with patch("questionary.checkbox") as mock_checkbox:
        mock_checkbox.return_value.ask.return_value = []

        wizard.configure_messagebus()

    assert wizard.state["messagebus"]["enabled"] is False


def test_save_config_writes_yaml():
    """Test that save_config writes valid YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        workspace.mkdir()  # Ensure workspace exists
        wizard = OnboardingWizard(workspace=workspace)

        wizard.state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }

        wizard.save_config()

        user_config_path = workspace / "config.user.yaml"
        assert user_config_path.exists()

        with open(user_config_path) as f:
            config = yaml.safe_load(f)

        assert config["llm"]["provider"] == "openai"
        assert config["messagebus"]["enabled"] is False
        assert config["default_agent"] == "pickle"  # auto-added


def test_save_config_no_system_file():
    """Test that save_config does NOT create config.system.yaml."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        workspace.mkdir()  # Ensure workspace exists
        wizard = OnboardingWizard(workspace=workspace)

        wizard.state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }

        wizard.save_config()

        system_config_path = workspace / "config.system.yaml"
        assert not system_config_path.exists()


def test_check_existing_workspace_returns_true_if_no_config():
    """Test check_existing_workspace returns True when config doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        wizard = OnboardingWizard(workspace=workspace)

        result = wizard.check_existing_workspace()

        assert result is True


def test_check_existing_workspace_prompts_if_config_exists():
    """Test check_existing_workspace prompts user when config exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")

        wizard = OnboardingWizard(workspace=workspace)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = True
            result = wizard.check_existing_workspace()

        mock_confirm.assert_called_once()
        assert result is True


def test_check_existing_workspace_returns_false_if_user_declines():
    """Test check_existing_workspace returns False if user says no."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")

        wizard = OnboardingWizard(workspace=workspace)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = wizard.check_existing_workspace()

        assert result is False


def test_run_includes_copy_default_assets():
    """Test that run() calls copy_default_assets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        wizard = OnboardingWizard(workspace=workspace)

        with (
            patch.object(wizard, "check_existing_workspace", return_value=True),
            patch.object(wizard, "setup_workspace"),
            patch.object(wizard, "configure_llm"),
            patch.object(wizard, "copy_default_assets") as mock_copy,
            patch.object(wizard, "configure_messagebus"),
            patch.object(wizard, "save_config", return_value=True),
        ):
            wizard.run()

        mock_copy.assert_called_once()


def test_run_returns_false_if_user_cancels_overwrite():
    """Test run returns False if user cancels at overwrite prompt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "config.user.yaml").write_text("llm: {}")

        wizard = OnboardingWizard(workspace=workspace)

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = wizard.run()

        assert result is False


def test_run_orchestrates_all_steps():
    """Test that run() calls all steps in order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        with (
            patch.object(wizard, "check_existing_workspace", return_value=True),
            patch.object(wizard, "setup_workspace") as mock_setup,
            patch.object(wizard, "configure_llm") as mock_llm,
            patch.object(wizard, "copy_default_assets") as mock_copy,
            patch.object(wizard, "configure_messagebus") as mock_bus,
            patch.object(wizard, "save_config", return_value=True) as mock_save,
        ):
            wizard.run()

        mock_setup.assert_called_once()
        mock_llm.assert_called_once()
        mock_copy.assert_called_once()
        mock_bus.assert_called_once()
        mock_save.assert_called_once()


def test_save_config_validates_with_pydantic():
    """Test that save_config validates config structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        # Missing required fields
        wizard.state = {
            "llm": {"provider": "openai"},  # missing model and api_key
            "messagebus": {"enabled": False},
        }

        with patch("questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = wizard.save_config()

        # Should handle validation error gracefully
        assert result is False or "error" in str(result).lower()


def test_discover_defaults_returns_empty_if_no_defaults():
    """Test _discover_defaults returns empty list if default_workspace missing."""
    wizard = OnboardingWizard()
    # Point to non-existent default workspace
    wizard.DEFAULT_WORKSPACE = Path("/nonexistent")

    result = wizard._discover_defaults("agents")
    assert result == []


def test_discover_defaults_returns_asset_names():
    """Test _discover_defaults returns names of assets in default_workspace."""
    wizard = OnboardingWizard()
    # Will use actual default_workspace if it exists
    result = wizard._discover_defaults("agents")
    # Just verify it returns a list
    assert isinstance(result, list)


def test_copy_asset_copies_directory():
    """Test _copy_asset copies asset from defaults to workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()

        wizard = OnboardingWizard(workspace=workspace)

        # Create a mock default asset
        mock_defaults = Path(tmpdir) / "defaults"
        mock_defaults.mkdir()
        mock_agent = mock_defaults / "agents" / "test-agent"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# Test Agent")

        wizard.DEFAULT_WORKSPACE = mock_defaults
        wizard._copy_asset("agents", "test-agent")

        # Verify copied
        copied = workspace / "agents" / "test-agent"
        assert copied.exists()
        assert (copied / "AGENT.md").read_text() == "# Test Agent"


def test_copy_asset_overwrites_existing():
    """Test _copy_asset overwrites existing asset."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        agents_dir = workspace / "agents"
        agents_dir.mkdir()

        # Create existing asset with old content
        existing = agents_dir / "test-agent"
        existing.mkdir()
        (existing / "AGENT.md").write_text("# Old Content")

        wizard = OnboardingWizard(workspace=workspace)

        # Create mock default with new content
        mock_defaults = Path(tmpdir) / "defaults"
        mock_defaults.mkdir()
        mock_agent = mock_defaults / "agents" / "test-agent"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# New Content")

        wizard.DEFAULT_WORKSPACE = mock_defaults
        wizard._copy_asset("agents", "test-agent")

        # Verify overwritten
        copied = workspace / "agents" / "test-agent"
        assert (copied / "AGENT.md").read_text() == "# New Content"


def test_copy_default_assets_prompts_user():
    """Test copy_default_assets shows multi-select and copies selected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        (workspace / "agents").mkdir()
        (workspace / "skills").mkdir()

        wizard = OnboardingWizard(workspace=workspace)

        # Create mock defaults
        mock_defaults = Path(tmpdir) / "defaults"
        mock_defaults.mkdir()
        mock_agent = mock_defaults / "agents" / "pickle"
        mock_agent.mkdir(parents=True)
        (mock_agent / "AGENT.md").write_text("# Pickle")

        wizard.DEFAULT_WORKSPACE = mock_defaults

        with patch("questionary.checkbox") as mock_checkbox:
            # User selects pickle agent, no skills
            mock_checkbox.return_value.ask.side_effect = [["pickle"], []]

            wizard.copy_default_assets()

        # Verify copied
        assert (workspace / "agents" / "pickle").exists()


def test_copy_default_assets_skips_if_no_defaults():
    """Test copy_default_assets does nothing if no default workspace."""
    wizard = OnboardingWizard()
    wizard.DEFAULT_WORKSPACE = Path("/nonexistent")

    with patch("questionary.checkbox") as mock_checkbox:
        wizard.copy_default_assets()

    # Should not prompt user
    mock_checkbox.assert_not_called()


class TestConfigureWebTools:
    """Tests for web tools onboarding configuration."""

    def test_configure_web_tools_none(self, tmp_path: Path, monkeypatch):
        """User selects nothing - no web tools in state."""
        wizard = OnboardingWizard(workspace=tmp_path)

        # Mock checkbox to return empty selection
        monkeypatch.setattr(
            "questionary.checkbox",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value=[])))
        )

        wizard.configure_web_tools()

        assert "websearch" not in wizard.state
        assert "webread" not in wizard.state
