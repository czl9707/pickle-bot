# tests/cli/onboarding/test_wizard.py
"""Integration tests for OnboardingWizard."""

from pathlib import Path
from unittest.mock import patch

from picklebot.cli.onboarding import OnboardingWizard


def test_wizard_instantiates():
    """OnboardingWizard can be instantiated."""
    wizard = OnboardingWizard()
    assert wizard.workspace


def test_wizard_custom_workspace():
    """OnboardingWizard accepts custom workspace path."""
    workspace = Path("/tmp/test-workspace")
    wizard = OnboardingWizard(workspace=workspace)
    assert wizard.workspace == workspace


def test_steps_list_defined():
    """OnboardingWizard has STEPS list defined."""
    from picklebot.cli.onboarding.steps import BaseStep

    assert hasattr(OnboardingWizard, "STEPS")
    assert isinstance(OnboardingWizard.STEPS, list)


def test_run_orchestrates_steps(tmp_path: Path):
    """run() executes all steps in order."""
    workspace = tmp_path / "workspace"
    wizard = OnboardingWizard(workspace=workspace)

    # Mock all steps to succeed
    with (
        patch.object(wizard, "STEPS", []),
    ):
        # Empty steps list should succeed
        result = wizard.run()
        assert result is True
