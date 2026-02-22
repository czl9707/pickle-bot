"""Tests for onboarding wizard."""

import tempfile
from pathlib import Path
from unittest.mock import patch

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
        # Model uses provider default - questionary returns default when user presses enter
        # Then api_key (no default), then api_base not prompted for openai
        mock_text.return_value.ask.side_effect = ["gpt-4o", "sk-test-key"]

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
        wizard = OnboardingWizard(workspace=workspace)

        wizard.state = {
            "llm": {"provider": "openai", "model": "gpt-4", "api_key": "test"},
            "messagebus": {"enabled": False},
        }

        wizard.save_config()

        system_config_path = workspace / "config.system.yaml"
        assert not system_config_path.exists()


def test_run_orchestrates_all_steps():
    """Test that run() calls all steps in order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "test-workspace"
        wizard = OnboardingWizard(workspace=workspace)

        with (
            patch.object(wizard, "setup_workspace") as mock_setup,
            patch.object(wizard, "configure_llm") as mock_llm,
            patch.object(wizard, "configure_messagebus") as mock_bus,
            patch.object(wizard, "save_config") as mock_save,
        ):
            wizard.run()

        mock_setup.assert_called_once()
        mock_llm.assert_called_once()
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
