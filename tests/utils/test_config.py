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


class TestAgentsPath:
    def test_resolves_relative_agents_path(self, minimal_llm_config):
        """Relative agents_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
            agents_path=Path("agents"),
        )
        assert config.agents_path == Path("/workspace/agents")

    def test_default_agents_path(self, minimal_llm_config):
        """Default agents_path should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
        )
        assert config.agents_path == Path("/workspace/agents")

    def test_rejects_absolute_agents_path(self, minimal_llm_config):
        """Absolute agents_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                default_agent="pickle",
                agents_path=Path("/etc/agents"),
            )
        assert "agents_path must be relative" in str(exc.value)

    def test_default_agent_required(self, minimal_llm_config):
        """default_agent is required."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
            )
        assert "default_agent" in str(exc.value)


class TestPathResolution:
    def test_resolves_relative_logging_path(self, minimal_llm_config):
        """Relative logging_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
            logging_path=Path(".logs"),
        )
        assert config.logging_path == Path("/workspace/.logs")

    def test_resolves_relative_history_path(self, minimal_llm_config):
        """Relative history_path should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
            history_path=Path(".history"),
        )
        assert config.history_path == Path("/workspace/.history")

    def test_uses_default_paths(self, minimal_llm_config):
        """Default paths should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
        )
        assert config.logging_path == Path("/workspace/.logs")
        assert config.history_path == Path("/workspace/.history")
        assert config.agents_path == Path("/workspace/agents")


class TestRejectsAbsolutePaths:
    def test_rejects_absolute_logging_path(self, minimal_llm_config):
        """Absolute logging_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                default_agent="pickle",
                logging_path=Path("/var/log"),
            )
        assert "logging_path must be relative" in str(exc.value)

    def test_rejects_absolute_history_path(self, minimal_llm_config):
        """Absolute history_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=minimal_llm_config,
                default_agent="pickle",
                history_path=Path("/var/history"),
            )
        assert "history_path must be relative" in str(exc.value)


class TestSkillsPath:
    def test_config_has_skills_path_default(self, minimal_llm_config):
        """Test Config has skills_path with default value."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
        )
        assert config.skills_path == Path("/workspace/skills")

    def test_config_accepts_custom_skills_path(self, minimal_llm_config):
        """Test Config can accept custom skills_path."""
        config = Config(
            workspace=Path("/workspace"),
            llm=minimal_llm_config,
            default_agent="pickle",
            skills_path=Path("custom/skills"),
        )
        assert config.skills_path == Path("/workspace/custom/skills")
