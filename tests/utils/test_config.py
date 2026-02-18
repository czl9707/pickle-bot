"""Tests for config path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import Config


class TestPathResolution:
    """Tests for path resolution against workspace."""

    def test_resolves_all_relative_paths_against_workspace(self, llm_config):
        """All relative paths should be resolved to absolute."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
        )
        assert config.agents_path == Path("/workspace/agents")
        assert config.skills_path == Path("/workspace/skills")
        assert config.crons_path == Path("/workspace/crons")
        assert config.logging_path == Path("/workspace/.logs")
        assert config.history_path == Path("/workspace/.history")
        assert config.memories_path == Path("/workspace/memories")

    def test_resolves_custom_relative_paths(self, llm_config):
        """Custom relative paths should be resolved against workspace."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
            agents_path=Path("custom/agents"),
            skills_path=Path("custom/skills"),
        )
        assert config.agents_path == Path("/workspace/custom/agents")
        assert config.skills_path == Path("/workspace/custom/skills")

    def test_rejects_absolute_agents_path(self, llm_config):
        """Absolute agents_path should raise ValidationError."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=llm_config,
                default_agent="test",
                agents_path=Path("/etc/agents"),
            )
        assert "agents_path must be relative" in str(exc.value)


class TestConfigValidation:
    """Tests for config validation rules."""

    def test_default_agent_required(self, llm_config):
        """default_agent is required."""
        with pytest.raises(ValidationError) as exc:
            Config(
                workspace=Path("/workspace"),
                llm=llm_config,
            )
        assert "default_agent" in str(exc.value)

    def test_telegram_config_allows_user_fields(self, llm_config):
        """TelegramConfig should accept allowed_user_ids and default_chat_id."""
        from picklebot.utils.config import TelegramConfig

        telegram = TelegramConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["123456"],
            default_chat_id="123456",
        )
        assert telegram.allowed_user_ids == ["123456"]
        assert telegram.default_chat_id == "123456"

    def test_discord_config_allows_user_fields(self, llm_config):
        """DiscordConfig should accept allowed_user_ids and default_chat_id."""
        from picklebot.utils.config import DiscordConfig

        discord = DiscordConfig(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=["789012"],
            default_chat_id="789012",
        )
        assert discord.allowed_user_ids == ["789012"]
        assert discord.default_chat_id == "789012"

    def test_messagebus_user_fields_default_to_empty(self, llm_config):
        """User fields should have sensible defaults."""
        from picklebot.utils.config import TelegramConfig, DiscordConfig

        telegram = TelegramConfig(enabled=True, bot_token="test-token")
        assert telegram.allowed_user_ids == []
        assert telegram.default_chat_id is None

        discord = DiscordConfig(enabled=True, bot_token="test-token")
        assert discord.allowed_user_ids == []
        assert discord.default_chat_id is None


class TestConfigDefaultChatId:
    """Tests for default_chat_id config field."""

    def test_telegram_config_has_default_chat_id(self):
        """TelegramConfig should have default_chat_id field."""
        from picklebot.utils.config import TelegramConfig

        config = TelegramConfig(
            bot_token="test-token",
            default_chat_id="123456",
        )
        assert config.default_chat_id == "123456"

    def test_discord_config_has_default_chat_id(self):
        """DiscordConfig should have default_chat_id field."""
        from picklebot.utils.config import DiscordConfig

        config = DiscordConfig(
            bot_token="test-token",
            default_chat_id="789012",
        )
        assert config.default_chat_id == "789012"
