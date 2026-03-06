"""Tests for config validation and path resolution."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import (
    Config,
    ChannelConfig,
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
    def test_platform_config_allows_user_ids(self, config_class, user_id):
        """Platform configs should accept allowed_user_ids."""
        config = config_class(
            enabled=True,
            bot_token="test-token",
            allowed_user_ids=[user_id],
        )
        assert config.allowed_user_ids == [user_id]

    @pytest.mark.parametrize("config_class", [TelegramConfig, DiscordConfig])
    def test_platform_config_defaults(self, config_class):
        """Platform config user fields should have sensible defaults."""
        config = config_class(enabled=True, bot_token="test-token")
        assert config.allowed_user_ids == []


class TestSessionHistoryLimits:
    """Tests for session history config fields."""

    def test_config_default_agent(self, llm_config):
        """Config should have default agent."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
        )
        assert config.default_agent == "test"

    def test_config_has_required_fields(self, llm_config):
        """Config should require certain fields."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="test",
        )
        assert config.default_agent == "test"


class TestChannelConfig:
    """Tests for messagebus configuration."""

    def test_messagebus_disabled_by_default(self, llm_config):
        """Test that messagebus is disabled by default."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="pickle",
        )
        assert not config.channels.enabled

    def test_messagebus_can_be_enabled_with_platform(self):
        """Test that messagebus can be enabled with platform config."""
        config = ChannelConfig(
            enabled=True,
            telegram=TelegramConfig(bot_token="test_token"),
        )
        assert config.enabled
        assert config.telegram is not None
        assert config.telegram.bot_token == "test_token"

    def test_messagebus_can_be_disabled(self):
        """Test that messagebus can be explicitly disabled."""
        config = ChannelConfig(enabled=False)
        assert not config.enabled

    def test_messagebus_integration_with_config(self, llm_config):
        """Test messagebus integration with full config."""
        config = Config(
            workspace=Path("/workspace"),
            llm=llm_config,
            default_agent="pickle",
            channels=ChannelConfig(
                enabled=True,
                telegram=TelegramConfig(bot_token="test_token"),
            ),
        )
        assert config.channels.enabled
        assert config.channels.telegram.bot_token == "test_token"


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
        """Config should include api configuration when provided."""
        config = Config(
            workspace=Path("/tmp/test-workspace"),
            llm=llm_config,
            default_agent="pickle",
            api=ApiConfig(host="0.0.0.0", port=3000),
        )
        assert config.api is not None
        assert config.api.host == "0.0.0.0"
        assert config.api.port == 3000

    def test_config_api_defaults_to_none(self, llm_config):
        """Config should have api=None by default."""
        config = Config(
            workspace=Path("/tmp/test-workspace"),
            llm=llm_config,
            default_agent="pickle",
        )
        assert config.api is None


class TestConfigReload:
    """Tests for config hot reload."""

    def test_reload_reads_updated_config(self, tmp_path, llm_config):
        """reload() should re-read config.user.yaml."""
        # Create initial config
        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        assert config.llm.model == "gpt-4"

        # Modify the file
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4o\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        # Reload
        config.reload()
        assert config.llm.model == "gpt-4o"

    def test_reload_returns_false_on_invalid_yaml(self, tmp_path, llm_config):
        """reload() should return False when config.user.yaml contains invalid YAML."""
        # Create initial valid config
        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        assert config.llm.model == "gpt-4"

        # Corrupt the file with invalid YAML
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
            "invalid_yaml: [unclosed\n"
        )

        # Reload should return False and not crash
        result = config.reload()
        assert result is False


class TestConfigHandler:
    """Tests for ConfigHandler file watching."""

    def test_handler_calls_reload_on_modify(self, tmp_path, llm_config):
        """ConfigHandler should call reload when config file changes."""
        from picklebot.utils.config import ConfigHandler
        from watchdog.events import FileModifiedEvent

        # Create config file
        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        handler = ConfigHandler(config)

        # Modify file
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4o\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        # Trigger the handler
        event = FileModifiedEvent(str(config_file))
        handler.on_modified(event)

        assert config.llm.model == "gpt-4o"

    def test_handler_ignores_other_files(self, tmp_path, llm_config):
        """ConfigHandler should ignore non-config files."""
        from picklebot.utils.config import ConfigHandler
        from watchdog.events import FileModifiedEvent

        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        handler = ConfigHandler(config)

        # Touch a different file
        other_file = tmp_path / "other.yaml"
        other_file.write_text("foo: bar")

        event = FileModifiedEvent(str(other_file))
        handler.on_modified(event)

        # Config should be unchanged
        assert config.llm.model == "gpt-4"


class TestConfigReloader:
    """Tests for ConfigReloader lifecycle."""

    def test_reloader_starts_and_stops_observer(self, tmp_path, llm_config):
        """ConfigReloader should start/stop watchdog observer."""
        from picklebot.utils.config import ConfigReloader

        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        reloader = ConfigReloader(config)

        # Start should create observer
        reloader.start()
        assert reloader._observer is not None
        assert reloader._observer.is_alive()

        # Stop should clean up
        reloader.stop()
        assert not hasattr(reloader, "_observer")

    def test_reloader_watches_config_changes(self, tmp_path, llm_config):
        """ConfigReloader should reload config on file change."""
        import time
        from picklebot.utils.config import ConfigReloader

        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        reloader = ConfigReloader(config)
        reloader.start()

        # Modify file
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4o\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        # Wait for event to propagate
        time.sleep(0.5)

        assert config.llm.model == "gpt-4o"

        reloader.stop()


class TestRoutingAndSourcesFields:
    """Tests for routing and sources config fields."""

    def test_config_has_routing_field(self, tmp_path):
        """Config should have routing field with bindings."""
        config_data = {
            "workspace": str(tmp_path),
            "llm": {"provider": "zai", "model": "test", "api_key": "test"},
            "default_agent": "pickle",
        }
        config = Config.model_validate(config_data)

        assert config.routing == {"bindings": []}

    def test_config_has_sources_field(self, tmp_path):
        """Config should have sources field for session cache."""
        config_data = {
            "workspace": str(tmp_path),
            "llm": {"provider": "zai", "model": "test", "api_key": "test"},
            "default_agent": "pickle",
        }
        config = Config.model_validate(config_data)

        assert config.sources == {}

    def test_config_merges_runtime_routing(self, tmp_path):
        """Runtime config should merge routing bindings."""
        # Write user config
        user_config = tmp_path / "config.user.yaml"
        user_config.write_text(
            """
llm:
  provider: zai
  model: test
  api_key: test
default_agent: pickle
"""
        )

        # Write runtime config
        runtime_config = tmp_path / "config.runtime.yaml"
        runtime_config.write_text(
            """
routing:
  bindings:
    - agent: cookie
      value: "telegram:123456"
sources:
  "telegram:123456":
    session_id: "uuid-abc"
"""
        )

        config = Config.load(tmp_path)

        assert len(config.routing["bindings"]) == 1
        assert config.routing["bindings"][0]["agent"] == "cookie"
        assert config.sources["telegram:123456"]["session_id"] == "uuid-abc"


def test_telegram_config_no_sessions_field():
    """TelegramConfig should not have sessions field."""
    from picklebot.utils.config import TelegramConfig

    config = TelegramConfig(bot_token="test")
    assert not hasattr(config, "sessions")


def test_telegram_config_no_default_chat_id():
    """TelegramConfig should not have default_chat_id field."""
    from picklebot.utils.config import TelegramConfig

    config = TelegramConfig(bot_token="test")
    assert not hasattr(config, "default_chat_id")


def test_discord_config_no_sessions_field():
    """DiscordConfig should not have sessions field."""
    from picklebot.utils.config import DiscordConfig

    config = DiscordConfig(bot_token="test")
    assert not hasattr(config, "sessions")


def test_discord_config_no_default_chat_id():
    """DiscordConfig should not have default_chat_id field."""
    from picklebot.utils.config import DiscordConfig

    config = DiscordConfig(bot_token="test")
    assert not hasattr(config, "default_chat_id")


def test_messagebus_config_no_default_platform():
    """ChannelConfig should not have default_platform field."""
    from picklebot.utils.config import ChannelConfig

    config = ChannelConfig()
    assert not hasattr(config, "default_platform")


class TestDefaultDeliverySource:
    """Tests for default_delivery_source config field."""

    def test_config_has_default_delivery_source(self, test_config):
        """Config should have optional default_delivery_source field."""
        assert hasattr(test_config, "default_delivery_source")
        assert test_config.default_delivery_source is None

    def test_config_default_delivery_source_roundtrip(self, tmp_path):
        """default_delivery_source should persist via set_runtime and reload."""
        # Create initial config file
        config_file = tmp_path / "config.user.yaml"
        config_file.write_text(
            "llm:\n  provider: openai\n  model: gpt-4\n  api_key: test\n"
            "default_agent: pickle\n"
        )

        config = Config.load(tmp_path)
        assert config.default_delivery_source is None

        # Set via set_runtime
        config.set_runtime("default_delivery_source", "telegram:user:123:chat:456")

        # Reload and verify
        config.reload()
        assert config.default_delivery_source == "telegram:user:123:chat:456"
