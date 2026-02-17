"""Tests for config validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from picklebot.utils.config import (
    Config,
    MessageBusConfig,
    TelegramConfig,
    DiscordConfig,
)


def test_messagebus_disabled_by_default(llm_config):
    """Test that messagebus is disabled by default."""
    config = Config(
        workspace=Path("/workspace"),
        llm=llm_config,
        default_agent="pickle",
    )
    assert not config.messagebus.enabled


def test_messagebus_enabled_requires_default_platform():
    """Test that enabled messagebus requires default_platform."""
    with pytest.raises(ValidationError, match="default_platform is required"):
        MessageBusConfig(enabled=True)


def test_messagebus_validates_platform_config():
    """Test that default_platform must have valid config."""
    with pytest.raises(ValidationError, match="telegram config is missing"):
        MessageBusConfig(enabled=True, default_platform="telegram")


def test_messagebus_valid_config():
    """Test valid messagebus configuration."""
    config = MessageBusConfig(
        enabled=True,
        default_platform="telegram",
        telegram=TelegramConfig(bot_token="test_token")
    )
    assert config.enabled
    assert config.default_platform == "telegram"


def test_messagebus_validates_discord_platform():
    """Test that discord platform requires discord config."""
    with pytest.raises(ValidationError, match="discord config is missing"):
        MessageBusConfig(enabled=True, default_platform="discord")


def test_messagebus_valid_discord_config():
    """Test valid discord configuration."""
    config = MessageBusConfig(
        enabled=True,
        default_platform="discord",
        discord=DiscordConfig(bot_token="test_token", channel_id="12345")
    )
    assert config.enabled
    assert config.default_platform == "discord"
    assert config.discord.channel_id == "12345"


def test_messagebus_validates_invalid_platform():
    """Test that invalid platform is rejected."""
    with pytest.raises(ValidationError, match="Invalid default_platform"):
        MessageBusConfig(enabled=True, default_platform="invalid")


def test_messagebus_can_be_disabled():
    """Test that messagebus can be explicitly disabled."""
    config = MessageBusConfig(enabled=False)
    assert not config.enabled


def test_messagebus_integration_with_config(llm_config):
    """Test messagebus integration with full config."""
    config = Config(
        workspace=Path("/workspace"),
        llm=llm_config,
        default_agent="pickle",
        messagebus=MessageBusConfig(
            enabled=True,
            default_platform="telegram",
            telegram=TelegramConfig(bot_token="test_token")
        )
    )
    assert config.messagebus.enabled
    assert config.messagebus.default_platform == "telegram"
    assert config.messagebus.telegram.bot_token == "test_token"
