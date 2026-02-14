"""Tests for config path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import Config, LLMConfig


@pytest.fixture
def minimal_llm_config():
    """Minimal LLM config for testing."""
    return LLMConfig(
        provider="test",
        model="test-model",
        api_key="test-key",
    )


class TestPathResolution:
    def test_resolves_relative_logging_path(self, minimal_llm_config):
        """Relative logging_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            logging_path=Path(".logs"),
        )
        assert config.logging_path == Path("/workspace/.logs")

    def test_resolves_relative_history_path(self, minimal_llm_config):
        """Relative history_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            history_path=Path(".history"),
        )
        assert config.history_path == Path("/workspace/.history")

    def test_uses_default_paths(self, minimal_llm_config):
        """Default paths should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
        )
        assert config.logging_path == Path("/workspace/.logs")
        assert config.history_path == Path("/workspace/.history")


class TestRejectsAbsolutePaths:
    def test_rejects_absolute_logging_path(self, minimal_llm_config):
        """Absolute logging_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                logging_path=Path("/var/log"),
            )
        assert "logging_path must be relative" in str(exc.value)

    def test_rejects_absolute_history_path(self, minimal_llm_config):
        """Absolute history_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                history_path=Path("/var/history"),
            )
        assert "history_path must be relative" in str(exc.value)
