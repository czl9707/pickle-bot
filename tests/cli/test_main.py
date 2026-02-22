"""Tests for CLI main module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from picklebot.cli.main import app

runner = CliRunner()


def test_init_command_exists():
    """Test that init command is registered."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert (
        "initialize" in result.output.lower() or "onboarding" in result.output.lower()
    )


def test_auto_onboarding_when_config_missing():
    """Test that onboarding is offered when config is missing."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "no-config"

        with patch("picklebot.cli.main.questionary.confirm") as mock_confirm:
            mock_confirm.return_value.ask.return_value = False
            result = runner.invoke(app, ["--workspace", str(workspace), "chat"])

        # Should prompt user for onboarding
        mock_confirm.assert_called_once()
        assert (
            "No configuration found" in mock_confirm.call_args[0][0]
            or "onboarding" in mock_confirm.call_args[0][0].lower()
        )

        # Should exit gracefully after user declines onboarding
        assert result.exit_code != 0
        assert (
            "init" in result.output.lower() or "configuration" in result.output.lower()
        )
