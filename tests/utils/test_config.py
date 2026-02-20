"""Tests for config validation and path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import (
    Config,
    MessageBusConfig,
    TelegramConfig,
    DiscordConfig,
)


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
        telegram = TelegramConfig(enabled=True, bot_token="test-token")
        assert telegram.allowed_user_ids == []
        assert telegram.default_chat_id is None

        discord = DiscordConfig(enabled=True, bot_token="test-token")
        assert discord.allowed_user_ids == []
        assert discord.default_chat_id is None


class TestSessionHistoryLimits:
    """Tests for session history config fields."""

    def test_config_default_history_limits(self, llm_config):
        """Config should have default history limits."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
        )

        assert config.chat_max_history == 50
        assert config.job_max_history == 500

    def test_config_custom_history_limits(self, llm_config):
        """Config should allow custom history limits."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
            chat_max_history=100,
            job_max_history=1000,
        )

        assert config.chat_max_history == 100
        assert config.job_max_history == 1000

    def test_config_history_limits_must_be_positive(self, llm_config):
        """Config should reject non-positive history limits."""
        with pytest.raises(ValidationError):
            Config(
                workspace=Path("/workspace"),
                llm=llm_config,
                default_agent="test",
                chat_max_history=0,
            )


class TestMessageBusConfig:
    """Tests for messagebus configuration."""

    def test_messagebus_disabled_by_default(self, llm_config):
        """Test that messagebus is disabled by default."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="pickle",
        )
        assert not config.messagebus.enabled

    def test_messagebus_enabled_requires_default_platform(self):
        """Test that enabled messagebus requires default_platform."""
        with pytest.raises(ValidationError, match="default_platform is required"):
            MessageBusConfig(enabled=True)

    def test_messagebus_validates_platform_config(self):
        """Test that default_platform must have valid config."""
        with pytest.raises(ValidationError, match="telegram config is missing"):
            MessageBusConfig(enabled=True, default_platform="telegram")

    def test_messagebus_valid_config(self):
        """Test valid messagebus configuration."""
        config = MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(bot_token="test_token"),
        )
        assert config.enabled
        assert config.default_platform == "telegram"

    def test_messagebus_validates_discord_platform(self):
        """Test that discord platform requires discord config."""
        with pytest.raises(ValidationError, match="discord config is missing"):
            MessageBusConfig(enabled=True, default_platform="discord")

    def test_messagebus_valid_discord_config(self):
        """Test valid discord configuration."""
        config = MessageBusConfig(
            enabled=True,
            default_platform="discord",
            discord=DiscordConfig(bot_token="test_token", channel_id="12345"),
        )
        assert config.enabled
        assert config.default_platform == "discord"
        assert config.discord.channel_id == "12345"

    def test_messagebus_validates_invalid_platform(self):
        """Test that invalid platform is rejected."""
        with pytest.raises(ValidationError, match="Invalid default_platform"):
            MessageBusConfig(enabled=True, default_platform="invalid")

    def test_messagebus_can_be_disabled(self):
        """Test that messagebus can be explicitly disabled."""
        config = MessageBusConfig(enabled=False)
        assert not config.enabled

    def test_messagebus_integration_with_config(self, llm_config):
        """Test messagebus integration with full config."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="pickle",
            messagebus=MessageBusConfig(
                enabled=True,
                default_platform="telegram",
                telegram=TelegramConfig(bot_token="test_token"),
            ),
        )
        assert config.messagebus.enabled
        assert config.messagebus.default_platform == "telegram"
        assert config.messagebus.telegram.bot_token == "test_token"
