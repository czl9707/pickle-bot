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
    api_base: str | None

    @field_validator("api_base")
    @classmethod
    def api_base_must_be_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("api_base must be a valid URL")
        return v


class AgentBehaviorConfig(BaseModel):
    """Agent behavior configuration."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)


class AgentConfigModel(BaseModel):
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


class SkillExecutionConfig(BaseModel):
    """Skill execution configuration."""

    timeout: int = Field(default=30, gt=0)
    max_concurrent: int = Field(default=5, gt=0)


class SkillsConfig(BaseModel):
    """Skills system configuration."""

    directory: str = "./skills"
    builtin: list[str] = Field(default_factory=lambda: ["echo", "get_time", "get_system_info"])
    execution: SkillExecutionConfig = Field(default_factory=SkillExecutionConfig)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    path: str = "logs/pickle-bot.log"
    rotation: str = "daily"
    retention: int = Field(default=30, gt=0)


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

    llm: LLMConfig
    agent: AgentConfigModel = Field(default_factory=AgentConfigModel)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def load(cls, config_dir: Path) -> "Config":
        """
        Load configuration from ~/.pickle-bot/.

        Args:
            config_dir: Path to config directory. Defaults to ~/.pickle-bot/

        Returns:
            Config instance with all settings loaded and validated

        Raises:
            FileNotFoundError: If config directory doesn't exist
            ValidationError: If configuration is invalid
        """

        if not config_dir.exists():
            raise FileNotFoundError(
                f"Config directory not found: {config_dir}\n"
                f"Please create it with: picklebot init"
            )

        # Load system config first (defaults), then user config (overrides)
        config_data: dict = {}

        system_config = config_dir / "config.system.yaml"
        user_config = config_dir / "config.user.yaml"

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
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
