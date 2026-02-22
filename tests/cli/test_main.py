"""Tests for CLI main module."""

from typer.testing import CliRunner

from picklebot.cli.main import app

runner = CliRunner()


def test_init_command_exists():
    """Test that init command is registered."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "initialize" in result.output.lower() or "onboarding" in result.output.lower()
