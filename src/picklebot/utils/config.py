"""Configuration management for pickle-bot."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


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


class AgentBehaviorConfig(BaseModel):
    """Agent behavior configuration."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)


class AgentConfig(BaseModel):
    """Agent-specific configuration."""

    name: str = Field(default="pickle", min_length=1)
    system_prompt: str = Field(default="You are a helpful AI assistant.")
    behavior: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v


class LoggingConfig(BaseModel):
    """Logging configuration."""

    path: str = Field(default=".logs")


class HistoryConfig(BaseModel):
    """History backend configuration."""

    path: str = Field(default=".history")


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
    agent: AgentConfig = Field(default_factory=AgentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)

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
