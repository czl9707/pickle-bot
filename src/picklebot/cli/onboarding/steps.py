"""Onboarding step classes."""

from pathlib import Path

import questionary
from rich.console import Console

from picklebot.provider.base import LLMProvider


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
    """Prompt user for LLM configuration."""

    def run(self, state: dict) -> bool:
        providers = LLMProvider.get_onboarding_providers()

        choices = [
            questionary.Choice(
                title=f"{p.display_name} (default: {p.default_model})",
                value=config_name,
            )
            for config_name, p in providers
        ]
        choices.append(questionary.Choice("Other (custom)", value="other"))

        provider = questionary.select("Select LLM provider:", choices=choices).ask()

        provider_cls = LLMProvider.name2provider[provider]
        model = questionary.text(
            "Model name:",
            default=provider_cls.default_model or "",
        ).ask()

        api_key = questionary.text("API key:").ask()

        api_base = questionary.text(
            "API base URL (optional):",
            default=provider_cls.api_base or "",
        ).ask()

        state["llm"] = {"provider": provider, "model": model, "api_key": api_key}
        if api_base:
            state["llm"]["api_base"] = api_base

        return True


class ConfigureExtraFunctionalityStep(BaseStep):
    """Prompt user for web tools and API configuration."""

    def run(self, state: dict) -> bool:
        selected = (
            questionary.checkbox(
                "Select extra functionality to enable:",
                choices=[
                    questionary.Choice("Web Search (Brave API)", value="websearch"),
                    questionary.Choice("Web Read (local scraping)", value="webread"),
                    questionary.Choice("API Server", value="api"),
                ],
            ).ask()
            or []
        )

        if "websearch" in selected:
            config = self._configure_websearch()
            if config:
                state["websearch"] = config

        if "webread" in selected:
            state["webread"] = {"provider": "crawl4ai"}

        if "api" in selected:
            state["api"] = {"enabled": True}

        return True

    def _configure_websearch(self) -> dict | None:
        """Prompt for web search configuration."""
        api_key = questionary.text("Brave Search API key:").ask()

        if not api_key:
            self.console.print(
                "[yellow]API key is required for web search. Skipping websearch config.[/yellow]"
            )
            return None

        return {
            "provider": "brave",
            "api_key": api_key,
        }


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
