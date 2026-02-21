"""Interactive onboarding wizard for pickle-bot."""

from pathlib import Path

import questionary


class OnboardingWizard:
    """Guides users through initial configuration."""

    def __init__(self, workspace: Path | None = None):
        """
        Initialize the wizard.

        Args:
            workspace: Path to workspace directory. Defaults to ~/.pickle-bot/
        """
        self.workspace = workspace or Path.home() / ".pickle-bot"
        self.state: dict = {}

    def setup_workspace(self) -> None:
        """Create workspace directory and required subdirectories."""
        self.workspace.mkdir(parents=True, exist_ok=True)

        subdirs = ["agents", "skills", "crons", "memories", ".history", ".logs"]
        for subdir in subdirs:
            (self.workspace / subdir).mkdir(exist_ok=True)

    def configure_llm(self) -> None:
        """Prompt user for LLM configuration."""
        provider = questionary.select(
            "Select LLM provider:",
            choices=["openai", "anthropic", "zai", "other"],
        ).ask()

        if provider == "other":
            provider = questionary.text("Enter provider name:").ask()

        model = questionary.text(
            "Model name:",
            default="gpt-4" if provider == "openai" else "claude-3-opus",
        ).ask()

        api_key = questionary.text("API key:").ask()

        api_base = questionary.text(
            "API base URL (optional, press Enter to skip):",
            default="",
        ).ask()

        self.state["llm"] = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
        }

        if api_base:
            self.state["llm"]["api_base"] = api_base
