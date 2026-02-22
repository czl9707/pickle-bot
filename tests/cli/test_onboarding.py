"""Tests for onboarding wizard."""

import tempfile
from pathlib import Path
from unittest.mock import patch

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
        mock_select.return_value.ask.return_value = "openai"
        mock_text.return_value.ask.side_effect = ["gpt-4", "sk-test-key", ""]

        wizard.configure_llm()

    assert wizard.state["llm"]["provider"] == "openai"
    assert wizard.state["llm"]["model"] == "gpt-4"
    assert wizard.state["llm"]["api_key"] == "sk-test-key"
    assert wizard.state["llm"].get("api_base") is None


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
            "12345",    # telegram allowed user ids
            "12345",    # telegram default chat id
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
