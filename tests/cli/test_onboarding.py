"""Tests for onboarding wizard."""

from picklebot.cli.onboarding import OnboardingWizard


def test_wizard_instantiates():
    """Test that OnboardingWizard can be instantiated."""
    wizard = OnboardingWizard()
    assert wizard.state == {}
