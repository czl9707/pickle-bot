"""Configuration management for pickle-bot."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Configuration Models
# ============================================================================


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str
    model: str
    api_key: str
    api_base: str | None = None

    @field_validator("api_base")
    @classmethod
    def api_base_must_be_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("api_base must be a valid URL")
        return v


class TelegramConfig(BaseModel):
    """Telegram platform configuration."""

    enabled: bool = True
    bot_token: str
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None  # Renamed from default_user_id


class DiscordConfig(BaseModel):
    """Discord platform configuration."""

    enabled: bool = True
    bot_token: str
    channel_id: str | None = None
    allowed_user_ids: list[str] = Field(default_factory=list)
    default_chat_id: str | None = None  # Renamed from default_user_id


class MessageBusConfig(BaseModel):
    """Message bus configuration."""

    enabled: bool = False
    default_platform: str | None = None
    telegram: TelegramConfig | None = None
    discord: DiscordConfig | None = None

    @model_validator(mode="after")
    def validate_default_platform(self) -> "MessageBusConfig":
        """Validate default_platform is configured when enabled."""
        if self.enabled:
            # default_platform is required when enabled
            if not self.default_platform:
                raise ValueError("default_platform is required when messagebus is enabled")

            # Verify default_platform has valid config
            if self.default_platform == "telegram" and not self.telegram:
                raise ValueError("default_platform is 'telegram' but telegram config is missing")
            if self.default_platform == "discord" and not self.discord:
                raise ValueError("default_platform is 'discord' but discord config is missing")
            if self.default_platform not in ["telegram", "discord"]:
                raise ValueError(f"Invalid default_platform: {self.default_platform}")

        return self


# ============================================================================
# Main Configuration Class
# ============================================================================


class Config(BaseModel):
    """
    Main configuration for pickle-bot.

    Configuration is loaded from ~/.pickle-bot/:
    1. config.system.yaml - System defaults (shipped with the app)
    2. config.user.yaml - User overrides (optional, overrides system)

    User config takes precedence over system config.
    """

    workspace: Path
    llm: LLMConfig
    default_agent: str
    agents_path: Path = Field(default=Path("agents"))
    skills_path: Path = Field(default=Path("skills"))
    logging_path: Path = Field(default=Path(".logs"))
    history_path: Path = Field(default=Path(".history"))
    crons_path: Path = Field(default=Path("crons"))
    memories_path: Path = Field(default=Path("memories"))
    messagebus: MessageBusConfig = Field(default_factory=MessageBusConfig)
    chat_max_history: int = Field(default=50, gt=0)
    job_max_history: int = Field(default=500, gt=0)

    @model_validator(mode="after")
    def resolve_paths(self) -> "Config":
        """Resolve relative paths to absolute using workspace."""
        for field_name in (
            "agents_path",
            "skills_path",
            "logging_path",
            "history_path",
            "crons_path",
            "memories_path",
        ):
            path = getattr(self, field_name)
            if path.is_absolute():
                raise ValueError(f"{field_name} must be relative, got: {path}")
            setattr(self, field_name, self.workspace / path)
        return self

    @classmethod
    def load(cls, workspace_dir: Path) -> "Config":
        """
        Load configuration from ~/.pickle-bot/.

        Args:
            workspace_dir: Path to workspace_dir directory. Defaults to ~/.pickle-bot/

        Returns:
            Config instance with all settings loaded and validated

        Raises:
            FileNotFoundError: If config directory doesn't exist
            ValidationError: If configuration is invalid
        """

        config_data: dict = {"workspace": workspace_dir}

        system_config = workspace_dir / "config.system.yaml"
        user_config = workspace_dir / "config.user.yaml"

        if system_config.exists():
            with open(system_config) as f:
                system_data = yaml.safe_load(f) or {}
            config_data.update(system_data)

        if user_config.exists():
            with open(user_config) as f:
                user_data = yaml.safe_load(f) or {}
            # Deep merge user config over system config
            config_data = cls._deep_merge(config_data, user_data)

        # Validate and create Config instance
        return cls.model_validate(config_data)

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge override dict into base dict.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
