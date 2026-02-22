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


def test_no_config_shows_init_instructions():
    """Test that missing config shows instructions to run init."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "no-config"

        result = runner.invoke(app, ["--workspace", str(workspace), "chat"])

        # Should exit with error
        assert result.exit_code == 1
        # Should show instructions to run init
        assert "picklebot init" in result.output.lower()


def test_init_skips_config_check():
    """Test that init command works without existing config."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "no-config"

        with patch("picklebot.cli.onboarding.OnboardingWizard.run") as mock_run:
            result = runner.invoke(app, ["--workspace", str(workspace), "init"])

        # Should call wizard exactly once
        mock_run.assert_called_once()
        # Should exit successfully
        assert result.exit_code == 0
