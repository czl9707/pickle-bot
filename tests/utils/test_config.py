"""Tests for config validation and path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import (
    Config,
    MessageBusConfig,
    TelegramConfig,
    DiscordConfig,
    ApiConfig,
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


class TestPlatformConfig:
    """Tests for platform-specific config (Telegram/Discord)."""

    @pytest.mark.parametrize(
        "config_class,user_id",
        [
            (TelegramConfig, "123456"),
            (DiscordConfig, "789012"),
        ],
    )
    def test_platform_config_allows_user_fields(self, config_class, user_id):
        """Platform configs should accept allowed_user_ids and default_chat_id."""
        config = config_class(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=[user_id],
            default_chat_id=user_id,
        )
        assert config.allowed_user_ids == [user_id]
        assert config.default_chat_id == user_id

    @pytest.mark.parametrize("config_class", [TelegramConfig, DiscordConfig])
    def test_platform_config_defaults(self, config_class):
        """Platform config user fields should have sensible defaults."""
        config = config_class(enabled=True, bot_token="test-token")
        assert config.allowed_user_ids == []
        assert config.default_chat_id is None

    @pytest.mark.parametrize("config_class", [TelegramConfig, DiscordConfig])
    def test_platform_config_has_sessions_field(self, config_class):
        """Platform configs should have sessions field for storing user session IDs."""
        config = config_class(enabled=True, bot_token="test-token")
        assert config.sessions == {}

        config_with_sessions = config_class(
            enabled=True, bot_token="test-token", sessions={"123456": "uuid-abc-123"}
        )
        assert config_with_sessions.sessions == {"123456": "uuid-abc-123"}


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
        assert config.max_history_file_size == 500

    def test_config_custom_history_limits(self, llm_config):
        """Config should allow custom history limits."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
            chat_max_history=100,
            job_max_history=1000,
            max_history_file_size=2000,
        )
        assert config.chat_max_history == 100
        assert config.job_max_history == 1000
        assert config.max_history_file_size == 2000

    @pytest.mark.parametrize(
        "field,value",
        [
            ("chat_max_history", 0),
            ("max_history_file_size", 0),
        ],
    )
    def test_positive_field_validation(self, llm_config, field, value):
        """Config should reject non-positive values for certain fields."""
        with pytest.raises(ValidationError):
            Config(
                workspace=Path("/workspace"),
                llm=llm_config,
                default_agent="test",
                **{field: value},
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

    @pytest.mark.parametrize(
        "platform,config_factory,error_match",
        [
            ("telegram", lambda: None, "telegram config is missing"),
            ("discord", lambda: None, "discord config is missing"),
            ("invalid", lambda: None, "Invalid default_platform"),
        ],
    )
    def test_messagebus_validates_platform_config(
        self, platform, config_factory, error_match
    ):
        """Test that messagebus validates platform config requirements."""
        kwargs = {"enabled": True, "default_platform": platform}
        if config_factory():
            kwargs[platform] = config_factory()
        with pytest.raises(ValidationError, match=error_match):
            MessageBusConfig(**kwargs)

    @pytest.mark.parametrize(
        "platform,config_factory",
        [
            ("telegram", lambda: TelegramConfig(bot_token="test_token")),
            (
                "discord",
                lambda: DiscordConfig(bot_token="test_token", channel_id="12345"),
            ),
        ],
    )
    def test_messagebus_valid_platform_config(self, platform, config_factory):
        """Test valid messagebus configuration for each platform."""
        config = MessageBusConfig(
            enabled=True, default_platform=platform, **{platform: config_factory()}
        )
        assert config.enabled
        assert config.default_platform == platform

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


class TestLLMConfig:
    """Tests for LLMConfig behavior fields."""

    def test_llm_config_has_behavior_defaults(self):
        """LLMConfig should have temperature and max_tokens with defaults."""
        from picklebot.utils.config import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
        )

        assert config.temperature == 0.7
        assert config.max_tokens == 2048


class TestApiConfig:
    """Tests for HTTP API configuration."""

    def test_config_has_api_config(self, llm_config):
        """Config should include api configuration."""
        config = Config(
            workspace=Path("/tmp/test-workspace"),
            llm=llm_config,
            default_agent="pickle",
            api=ApiConfig(enabled=True, host="0.0.0.0", port=3000),
        )
        assert config.api.enabled is True
        assert config.api.host == "0.0.0.0"
        assert config.api.port == 3000
