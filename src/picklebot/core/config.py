"""Configuration management for pickle-bot."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str
    model: str
    api_key: str
    api_base: str = "https://api.openai.com/v1"


class AgentConfigModel(BaseModel):
    """Agent-specific configuration."""

    name: str = "pickle-bot"
    system_prompt: str = "You are a helpful AI assistant."
    max_history: int = 50


class SkillsConfig(BaseModel):
    """Skills system configuration."""

    directory: str = "./skills"
    auto_load: bool = True


class AgentConfig(BaseModel):
    """Main configuration for pickle-bot."""

    llm: LLMConfig
    agent: AgentConfigModel = Field(default_factory=AgentConfigModel)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AgentConfig":
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to config file. Defaults to config/default.yaml

        Returns:
            AgentConfig instance
        """
        # Load environment variables from .env
        load_dotenv()

        # Default config path
        if config_path is None:
            config_path = Path("config/default.yaml")

        # Read and parse YAML config
        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        # Interpolate environment variables
        config_data = cls._interpolate_env_vars(config_data)

        return cls(**config_data)

    @staticmethod
    def _interpolate_env_vars(data: dict) -> dict:
        """
        Recursively interpolate environment variables in config values.

        Supports ${VAR_NAME} syntax.
        """
        result = {}

        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = AgentConfig._interpolate_env_vars(value)
            elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                result[key] = os.getenv(env_var, value)
            else:
                result[key] = value

        return result
