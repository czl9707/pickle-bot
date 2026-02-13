"""Logging configuration for pickle-bot."""

import logging

from picklebot.utils.config import Config


def setup_logging(config: Config) -> None:
    """
    Set up logging for pickle-bot.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
    """

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(format_str)

    file_handler = logging.FileHandler(config.workspace.joinpath(config.logging.path))
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger("picklebot")
    root_logger.setLevel("DEBUG")
    root_logger.addHandler(file_handler)
