"""Onboarding step classes."""

from pathlib import Path

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
