"""Onboarding wizard orchestrator."""

from pathlib import Path

from picklebot.cli.onboarding.steps import BaseStep


class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = (
        Path(__file__).parent.parent.parent.parent / "default_workspace"
    )

    STEPS: list[type[BaseStep]] = []

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".pickle-bot"

    def run(self) -> bool:
        """Run all onboarding steps. Returns True if successful."""
        raise NotImplementedError
