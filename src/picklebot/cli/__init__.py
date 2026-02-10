"""CLI interface for pickle-bot."""

from picklebot.cli.main import app
from picklebot.cli.skills import skills_app

__all__ = ["app", "skills_app"]
