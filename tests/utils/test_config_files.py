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


class TestConfigSetters:
    """Tests for config setter methods."""

    def test_set_user_creates_file(self, tmp_path):
        """set_user creates config.user.yaml if it doesn't exist."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text(
            "default_agent: system-agent\n"
            "llm:\n"
            "  provider: openai\n"
            "  model: gpt-4\n"
            "  api_key: system-key\n"
        )

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        # File should exist
        user_config = tmp_path / "config.user.yaml"
        assert user_config.exists()

        # Content should be correct
        data = yaml.safe_load(user_config.read_text())
        assert data["default_agent"] == "my-agent"

    def test_set_user_preserves_existing(self, tmp_path):
        """set_user preserves other fields in config.user.yaml."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text(
            "default_agent: system-agent\n"
            "llm:\n"
            "  provider: openai\n"
            "  model: gpt-4\n"
            "  api_key: system-key\n"
        )

        user_config = tmp_path / "config.user.yaml"
        user_config.write_text("chat_max_history: 100\n")

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        # Both fields should be present
        data = yaml.safe_load(user_config.read_text())
        assert data["default_agent"] == "my-agent"
        assert data["chat_max_history"] == 100

    def test_set_user_updates_in_memory(self, tmp_path):
        """set_user updates the in-memory config object."""
        system_config = tmp_path / "config.system.yaml"
        system_config.write_text(
            "default_agent: system-agent\n"
            "llm:\n"
            "  provider: openai\n"
            "  model: gpt-4\n"
            "  api_key: system-key\n"
        )

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        assert config.default_agent == "my-agent"
