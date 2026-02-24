"""Onboarding step classes."""

from pathlib import Path

import questionary
from rich.console import Console


class BaseStep:
    """Base class for onboarding steps."""

    def __init__(self, workspace: Path, console: Console, defaults: Path):
        self.workspace = workspace
        self.console = console
        self.defaults = defaults

    def run(self, state: dict) -> bool:
        """Execute step. Return True on success, False to abort."""
        raise NotImplementedError


class CheckWorkspaceStep(BaseStep):
    """Check if workspace exists and prompt for overwrite confirmation."""

    def run(self, state: dict) -> bool:
        config_path = self.workspace / "config.user.yaml"

        if config_path.exists():
            self.console.print(
                f"\n[yellow]Workspace already exists at {self.workspace}[/yellow]"
            )

            proceed = questionary.confirm(
                "This will overwrite your existing configuration. Continue?",
                default=False,
            ).ask()

            return proceed

        return True
