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
