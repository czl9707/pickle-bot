"""Tests for onboarding wizard."""

import tempfile
from pathlib import Path

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
