"""Onboarding step classes."""

import shutil
from pathlib import Path

import questionary
import yaml
from pydantic import ValidationError
from rich.console import Console

from picklebot.provider.llm import LLMProvider
from picklebot.utils.config import Config


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
    """Copy selected default agents and skills to workspace."""

    # Map asset type to definition filename
    DEFINITION_FILES = {
        "agents": "AGENT.md",
        "skills": "SKILL.md",
    }

    def run(self, state: dict) -> bool:
        default_agents = self._discover_defaults("agents")
        default_skills = self._discover_defaults("skills")

        if not default_agents and not default_skills:
            return True

        self.console.print("\n[bold]Default assets available:[/bold]")

        selected_agents = (
            questionary.checkbox(
                "Select agents to copy (will overwrite existing):",
                choices=[
                    questionary.Choice(
                        title=f"{name} - {desc}" if desc else name,
                        value=name,
                        checked=True,
                    )
                    for name, desc in default_agents
                ],
            ).ask()
            or []
        )

        selected_skills = (
            questionary.checkbox(
                "Select skills to copy (will overwrite existing):",
                choices=[
                    questionary.Choice(
                        title=f"{name} - {desc}" if desc else name,
                        value=name,
                        checked=True,
                    )
                    for name, desc in default_skills
                ],
            ).ask()
            or []
        )

        for name in selected_agents:
            self._copy_asset("agents", name)
        for name in selected_skills:
            self._copy_asset("skills", name)

        return True

    def _discover_defaults(self, asset_type: str) -> list[tuple[str, str]]:
        """List available default assets with their descriptions.

        Returns:
            List of (name, description) tuples, sorted by name.
        """
        path = self.defaults / asset_type
        if not path.exists():
            return []

        results = []
        for d in sorted(path.iterdir(), key=lambda x: x.name):
            if d.is_dir():
                name = d.name
                desc = self._get_asset_description(asset_type, name)
                results.append((name, desc))
        return results

    def _get_asset_description(self, asset_type: str, name: str) -> str:
        """Extract description from asset's definition file frontmatter."""
        filename = self.DEFINITION_FILES.get(asset_type)
        if not filename:
            return ""

        def_file = self.defaults / asset_type / name / filename
        if not def_file.exists():
            return ""

        try:
            content = def_file.read_text()
            # Parse YAML frontmatter
            if content.startswith("---\n"):
                end = content.find("\n---\n", 4)
                if end != -1:
                    frontmatter_str = content[4:end]
                    frontmatter = yaml.safe_load(frontmatter_str)
                    if isinstance(frontmatter, dict):
                        return frontmatter.get("description", "")
        except Exception:
            pass

        return ""

    def _copy_asset(self, asset_type: str, name: str) -> None:
        """Copy a single asset from defaults to workspace."""
        src = self.defaults / asset_type / name
        dst = self.workspace / asset_type / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


class ConfigureMessageBusStep(BaseStep):
    """Prompt user for MessageBus configuration."""

    def run(self, state: dict) -> bool:
        platforms = questionary.checkbox(
            "Select messaging platforms to enable:",
            choices=["telegram", "discord"],
        ).ask()

        if not platforms:
            state["messagebus"] = {"enabled": False}
            return True

        state["messagebus"] = {
            "enabled": True,
            "default_platform": platforms[0],
        }

        if "telegram" in platforms:
            state["messagebus"]["telegram"] = self._configure_telegram()

        if "discord" in platforms:
            state["messagebus"]["discord"] = self._configure_discord()

        return True

    def _configure_telegram(self) -> dict:
        """Prompt for Telegram-specific configuration."""
        bot_token = questionary.text("Telegram bot token:").ask()

        allowed_users = questionary.text(
            "Allowed user IDs (comma-separated, or press Enter for open access):",
            default="",
        ).ask()

        default_chat = questionary.text(
            "Default chat ID to proactively post to (optional, press Enter to skip):",
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


class SaveConfigStep(BaseStep):
    """Write configuration to config.user.yaml."""

    def run(self, state: dict) -> bool:
        # Set default_agent if not provided
        if "default_agent" not in state:
            state["default_agent"] = "pickle"

        # Validate config structure
        try:
            config_data = {"workspace": self.workspace}
            config_data.update(state)
            Config.model_validate(config_data)
        except ValidationError as e:
            self.console.print("\n[red]Configuration validation failed:[/red]")
            for error in e.errors():
                self.console.print(f"  - {error['loc'][0]}: {error['msg']}")
            return False

        # Write user config
        user_config_path = self.workspace / "config.user.yaml"
        with open(user_config_path, "w") as f:
            yaml.dump(state, f, default_flow_style=False)

        return True
