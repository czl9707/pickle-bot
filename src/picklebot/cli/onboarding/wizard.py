# src/picklebot/cli/onboarding/wizard.py
"""Onboarding wizard orchestrator."""

from pathlib import Path

from rich.console import Console

from picklebot.cli.onboarding.steps import (
    BaseStep,
    CheckWorkspaceStep,
    ConfigureExtraFunctionalityStep,
    ConfigureLLMStep,
    ConfigureMessageBusStep,
    CopyDefaultAssetsStep,
    SaveConfigStep,
    SetupWorkspaceStep,
)


class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = Path(__file__).parent.parent.parent.parent.parent / "default_workspace"

    STEPS: list[type[BaseStep]] = [
        CheckWorkspaceStep,
        SetupWorkspaceStep,
        ConfigureLLMStep,
        ConfigureExtraFunctionalityStep,
        ConfigureMessageBusStep,
        CopyDefaultAssetsStep,
        SaveConfigStep,
    ]

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".pickle-bot"

    def run(self) -> bool:
        """Run all onboarding steps. Returns True if successful."""
        console = Console()
        state: dict = {}

        console.print("\n[bold cyan]Welcome to Pickle-Bot![/bold cyan]")
        console.print("Let's set up your configuration.\n")

        for step_cls in self.STEPS:
            step = step_cls(self.workspace, console, self.DEFAULT_WORKSPACE)
            if not step.run(state):
                console.print("[yellow]Onboarding cancelled.[/yellow]")
                return False

        console.print("\n[green]Configuration saved![/green]")
        console.print(f"Config file: {self.workspace / 'config.user.yaml'}")
        console.print("Edit this file to make changes.\n")
        return True
