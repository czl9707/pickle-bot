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


class SetupWorkspaceStep(BaseStep):
    """Create workspace directory and required subdirectories."""

    def run(self, state: dict) -> bool:
        self.workspace.mkdir(parents=True, exist_ok=True)

        subdirs = ["agents", "skills", "crons", "memories", ".history", ".logs"]
        for subdir in subdirs:
            (self.workspace / subdir).mkdir(exist_ok=True)

        return True


class ConfigureLLMStep(BaseStep):
    """Configure LLM provider, model, and API key."""

    def run(self, state: dict) -> bool:
        raise NotImplementedError


class ConfigureExtraFunctionalityStep(BaseStep):
    """Configure optional features like websearch, webread, and API."""

    def run(self, state: dict) -> bool:
        raise NotImplementedError


class CopyDefaultAssetsStep(BaseStep):
    """Copy default agents and skills to workspace."""

    def run(self, state: dict) -> bool:
        raise NotImplementedError


class ConfigureMessageBusStep(BaseStep):
    """Configure message bus platforms (Telegram, Discord)."""

    def run(self, state: dict) -> bool:
        raise NotImplementedError


class SaveConfigStep(BaseStep):
    """Write config.user.yaml file."""

    def run(self, state: dict) -> bool:
        raise NotImplementedError
