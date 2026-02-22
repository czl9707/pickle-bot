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


class ApiConfig(BaseModel):
    """HTTP API configuration."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = Field(default=8000, gt=0, lt=65536)


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
                raise ValueError(
                    "default_platform is required when messagebus is enabled"
                )

            # Verify default_platform has valid config
            if self.default_platform == "telegram" and not self.telegram:
                raise ValueError(
                    "default_platform is 'telegram' but telegram config is missing"
                )
            if self.default_platform == "discord" and not self.discord:
                raise ValueError(
                    "default_platform is 'discord' but discord config is missing"
                )
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
    1. config.user.yaml - User configuration (required fields: llm, default_agent)
    2. config.runtime.yaml - Runtime state (optional, overrides user)

    Runtime config takes precedence over user config. Pydantic defaults are used
    for optional fields not specified in config files.
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
    api: ApiConfig = Field(default_factory=ApiConfig)
    chat_max_history: int = Field(default=50, gt=0)
    job_max_history: int = Field(default=500, gt=0)
    max_history_file_size: int = Field(default=500, gt=0)

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

        user_config = workspace_dir / "config.user.yaml"
        runtime_config = workspace_dir / "config.runtime.yaml"

        # Deep merge user config
        if user_config.exists():
            with open(user_config) as f:
                user_data = yaml.safe_load(f) or {}
            config_data = cls._deep_merge(config_data, user_data)

        # Deep merge runtime config (overrides user)
        if runtime_config.exists():
            with open(runtime_config) as f:
                runtime_data = yaml.safe_load(f) or {}
            config_data = cls._deep_merge(config_data, runtime_data)

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

    def _set_nested(self, obj: dict, key: str, value: Any) -> None:
        """Set a nested value in a dict using dot notation."""
        keys = key.split(".")
        for k in keys[:-1]:
            if k not in obj or not isinstance(obj[k], dict):
                obj[k] = {}
            obj = obj[k]
        obj[keys[-1]] = value

    def _set_config_value(self, config_path: Path, key: str, value: Any) -> None:
        """
        Update a config value in a YAML file.

        Args:
            config_path: Path to the YAML file
            key: Config key (supports dot notation for nested values)
            value: New value
        """
        # Load existing or start fresh
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        # Update the key (supports nested via dot notation)
        self._set_nested(data, key, value)

        # Write back
        with open(config_path, "w") as f:
            yaml.dump(data, f)

    def _update_in_memory(self, key: str, value: Any) -> None:
        """Update in-memory config, supporting nested attributes."""
        keys = key.split(".")
        obj = self
        for k in keys[:-1]:
            obj = getattr(obj, k)
        setattr(obj, keys[-1], value)

    def set_user(self, key: str, value: Any) -> None:
        """
        Update a config value in config.user.yaml.

        Args:
            key: Config key (supports dot notation, e.g., "llm.api_key")
            value: New value
        """
        self._set_config_value(self.workspace / "config.user.yaml", key, value)
        self._update_in_memory(key, value)

    def set_runtime(self, key: str, value: Any) -> None:
        """
        Update a runtime value in config.runtime.yaml.

        Args:
            key: Config key (supports dot notation, e.g., "session.id")
            value: New value
        """
        self._set_config_value(self.workspace / "config.runtime.yaml", key, value)
        self._update_in_memory(key, value)
