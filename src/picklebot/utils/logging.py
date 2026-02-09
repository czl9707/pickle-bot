"""Logging configuration for pickle-bot."""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """
    Set up logging for pickle-bot.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure logging format
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(format_str)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger configuration
    root_logger = logging.getLogger("picklebot")
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
