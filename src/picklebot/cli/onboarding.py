"""Interactive onboarding wizard for pickle-bot."""

import shutil
from pathlib import Path

import questionary
import yaml
from pydantic import ValidationError
from rich.console import Console

from picklebot.provider.base import LLMProvider
from picklebot.utils.config import Config


class OnboardingWizard:
    """Guides users through initial configuration."""

    DEFAULT_WORKSPACE = Path(__file__).parent.parent.parent / "default_workspace"

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
        """Prompt user for LLM configuration using auto-discovered providers."""
        # Get providers for onboarding
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

        # Get provider class for defaults
        provider_cls = LLMProvider.name2provider[provider]

        # Model with provider default
        model = questionary.text(
            "Model name:",
            default=provider_cls.default_model,
        ).ask()

        # API key with env var hint
        env_hint = f" (or set {provider_cls.env_var})" if provider_cls.env_var else ""
        api_key = questionary.text(f"API key{env_hint}:").ask()

        # API base (only for "other" or if provider has default)
        api_base = ""
        if provider == "other" or provider_cls.api_base:
            api_base = questionary.text(
                "API base URL (optional):",
                default=provider_cls.api_base or "",
            ).ask()

        self.state["llm"] = {"provider": provider, "model": model, "api_key": api_key}
        if api_base:
            self.state["llm"]["api_base"] = api_base

    def configure_messagebus(self) -> None:
        """Prompt user for MessageBus configuration."""
        platforms = questionary.checkbox(
            "Select messaging platforms to enable:",
            choices=["telegram", "discord"],
        ).ask()

        if not platforms:
            self.state["messagebus"] = {"enabled": False}
            return

        self.state["messagebus"] = {
            "enabled": True,
            "default_platform": platforms[0],
        }

        if "telegram" in platforms:
            self.state["messagebus"]["telegram"] = self._configure_telegram()

        if "discord" in platforms:
            self.state["messagebus"]["discord"] = self._configure_discord()

    def _configure_telegram(self) -> dict:
        """Prompt for Telegram-specific configuration."""
        bot_token = questionary.text("Telegram bot token:").ask()

        allowed_users = questionary.text(
            "Allowed user IDs (comma-separated, or press Enter for open access):",
            default="",
        ).ask()

        default_chat = questionary.text(
            "Default chat ID (optional, press Enter to skip):",
            default="",
        ).ask()

        config: dict = {
            "enabled": True,
            "bot_token": bot_token,
            "allowed_user_ids": [],
        }

        if allowed_users:
            config["allowed_user_ids"] = [
                uid.strip() for uid in allowed_users.split(",") if uid.strip()
            ]

        if default_chat:
            config["default_chat_id"] = default_chat

        return config

    def _configure_discord(self) -> dict:
        """Prompt for Discord-specific configuration."""
        bot_token = questionary.text("Discord bot token:").ask()

        channel_id = questionary.text(
            "Channel ID to listen on (optional, press Enter for all channels):",
            default="",
        ).ask()

        allowed_users = questionary.text(
            "Allowed user IDs (comma-separated, or press Enter for open access):",
            default="",
        ).ask()

        default_chat = questionary.text(
            "Default channel ID for proactive posts (optional):",
            default="",
        ).ask()

        config: dict = {
            "enabled": True,
            "bot_token": bot_token,
            "allowed_user_ids": [],
        }

        if channel_id:
            config["channel_id"] = channel_id

        if allowed_users:
            config["allowed_user_ids"] = [
                uid.strip() for uid in allowed_users.split(",") if uid.strip()
            ]

        if default_chat:
            config["default_chat_id"] = default_chat

        return config

    def save_config(self) -> bool:
        """
        Write configuration to config.user.yaml.

        Returns:
            True if save succeeded, False if validation failed.
        """
        # Set default_agent if not provided
        if "default_agent" not in self.state:
            self.state["default_agent"] = "pickle"

        # Validate config structure
        try:
            config_data = {"workspace": self.workspace}
            config_data.update(self.state)
            Config.model_validate(config_data)
        except ValidationError as e:
            console = Console()
            console.print("\n[red]Configuration validation failed:[/red]")
            for error in e.errors():
                console.print(f"  - {error['loc'][0]}: {error['msg']}")
            return False

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Write user config
        user_config_path = self.workspace / "config.user.yaml"
        with open(user_config_path, "w") as f:
            yaml.dump(self.state, f, default_flow_style=False)

        return True

    def check_existing_workspace(self) -> bool:
        """Check if workspace exists and prompt for overwrite confirmation."""
        config_path = self.workspace / "config.user.yaml"

        if config_path.exists():
            console = Console()
            console.print(
                f"\n[yellow]Workspace already exists at {self.workspace}[/yellow]"
            )

            proceed = questionary.confirm(
                "This will overwrite your existing configuration. Continue?",
                default=False,
            ).ask()

            return proceed

        return True

    def run(self) -> bool:
        """Run the complete onboarding flow. Returns True if successful."""
        console = Console()

        # Check for existing workspace
        if not self.check_existing_workspace():
            console.print("[yellow]Onboarding cancelled.[/yellow]")
            return False

        console.print("\n[bold cyan]Welcome to Pickle-Bot![/bold cyan]")
        console.print("Let's set up your configuration.\n")

        self.setup_workspace()
        self.configure_llm()
        self.copy_default_assets()
        self.configure_messagebus()

        if self.save_config():
            console.print("\n[green]Configuration saved![/green]")
            console.print(f"Config file: {self.workspace / 'config.user.yaml'}")
            console.print("Edit this file to make changes.\n")
            return True

        return False

    def copy_default_assets(self) -> None:
        """Copy selected default agents and skills to workspace."""
        default_agents = self._discover_defaults("agents")
        default_skills = self._discover_defaults("skills")

        if not default_agents and not default_skills:
            return

        console = Console()
        console.print("\n[bold]Default assets available:[/bold]")

        # Multi-select for agents
        selected_agents = (
            questionary.checkbox(
                "Select agents to copy (will overwrite existing):",
                choices=[
                    questionary.Choice(f"agents/{name}", value=name, checked=True)
                    for name in sorted(default_agents)
                ],
            ).ask()
            or []
        )

        # Multi-select for skills
        selected_skills = (
            questionary.checkbox(
                "Select skills to copy (will overwrite existing):",
                choices=[
                    questionary.Choice(f"skills/{name}", value=name, checked=True)
                    for name in sorted(default_skills)
                ],
            ).ask()
            or []
        )

        # Copy selected
        for name in selected_agents:
            self._copy_asset("agents", name)
        for name in selected_skills:
            self._copy_asset("skills", name)

    def _discover_defaults(self, asset_type: str) -> list[str]:
        """List available default assets of a type."""
        path = self.DEFAULT_WORKSPACE / asset_type
        if not path.exists():
            return []
        return [d.name for d in path.iterdir() if d.is_dir()]

    def _copy_asset(self, asset_type: str, name: str) -> None:
        """Copy a single asset from defaults to workspace."""
        src = self.DEFAULT_WORKSPACE / asset_type / name
        dst = self.workspace / asset_type / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
