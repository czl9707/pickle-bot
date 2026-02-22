"""Tests for config file handling."""

import pytest
import yaml
from pathlib import Path
from picklebot.utils.config import Config


class TestConfigFiles:
    """Tests for config file paths and loading."""

    def test_loads_runtime_config(self, tmp_path):
        """Runtime config is merged on top of user config."""
        # Create minimal system config with required llm field
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text(
            "default_agent: system-agent\n"
            "llm:\n"
            "  provider: openai\n"
            "  model: gpt-4\n"
            "  api_key: system-key\n"
        )

        # Create user config
        user_config = tmp_path / "config.user.yaml"
        user_config.write_text("default_agent: user-agent\n")

        # Create runtime config
        runtime_config = tmp_path / "config.runtime.yaml"
        runtime_config.write_text("default_agent: runtime-agent\n")

        config = Config.load(tmp_path)

        # Runtime should win
        assert config.default_agent == "runtime-agent"

    def test_runtime_config_optional(self, tmp_path):
        """Config loads fine without runtime config."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text(
            "default_agent: system-agent\n"
            "llm:\n"
            "  provider: openai\n"
            "  model: gpt-4\n"
            "  api_key: system-key\n"
        )

        config = Config.load(tmp_path)
        assert config.default_agent == "system-agent"
