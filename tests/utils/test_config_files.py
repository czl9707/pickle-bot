"""Tests for config file handling."""

import pytest
import yaml
from pathlib import Path
from picklebot.utils.config import Config


def _create_user_config(tmp_path: Path, **kwargs) -> None:
    """Helper to create a valid config.user.yaml."""
    defaults = {
        "default_agent": "test-agent",
        "llm": {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key",
        },
    }
    defaults.update(kwargs)
    user_config = tmp_path / "config.user.yaml"
    user_config.write_text(yaml.dump(defaults))


class TestConfigFiles:
    """Tests for config file paths and loading."""

    def test_loads_runtime_config(self, tmp_path):
        """Runtime config is merged on top of user config."""
        # Create user config
        _create_user_config(tmp_path, default_agent="user-agent")

        # Create runtime config
        runtime_config = tmp_path / "config.runtime.yaml"
        runtime_config.write_text("default_agent: runtime-agent\n")

        config = Config.load(tmp_path)

        # Runtime should win
        assert config.default_agent == "runtime-agent"

    def test_runtime_config_optional(self, tmp_path):
        """Config loads fine without runtime config."""
        _create_user_config(tmp_path, default_agent="my-agent")

        config = Config.load(tmp_path)
        assert config.default_agent == "my-agent"


class TestConfigSetters:
    """Tests for config setter methods."""

    def test_set_user_creates_file(self, tmp_path):
        """set_user creates config.user.yaml if it doesn't exist."""
        _create_user_config(tmp_path)

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        # Content should be correct
        user_config = tmp_path / "config.user.yaml"
        data = yaml.safe_load(user_config.read_text())
        assert data["default_agent"] == "my-agent"

    def test_set_user_preserves_existing(self, tmp_path):
        """set_user preserves other fields in config.user.yaml."""
        _create_user_config(tmp_path, chat_max_history=100)

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        # Both fields should be present
        user_config = tmp_path / "config.user.yaml"
        data = yaml.safe_load(user_config.read_text())
        assert data["default_agent"] == "my-agent"
        assert data["chat_max_history"] == 100

    def test_set_user_updates_in_memory(self, tmp_path):
        """set_user updates the in-memory config object."""
        _create_user_config(tmp_path)

        config = Config.load(tmp_path)
        config.set_user("default_agent", "my-agent")

        assert config.default_agent == "my-agent"

    def test_set_runtime_creates_file(self, tmp_path):
        """set_runtime creates config.runtime.yaml if it doesn't exist."""
        _create_user_config(tmp_path)

        config = Config.load(tmp_path)
        config.set_runtime("default_agent", "runtime-agent")

        # File should exist
        runtime_config = tmp_path / "config.runtime.yaml"
        assert runtime_config.exists()

        # Content should be correct
        data = yaml.safe_load(runtime_config.read_text())
        assert data["default_agent"] == "runtime-agent"

    def test_set_runtime_updates_in_memory(self, tmp_path):
        """set_runtime updates the in-memory config object."""
        _create_user_config(tmp_path)

        config = Config.load(tmp_path)
        config.set_runtime("default_agent", "runtime-agent")

        assert config.default_agent == "runtime-agent"
