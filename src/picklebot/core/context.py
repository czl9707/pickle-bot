from dataclasses import dataclass

from picklebot.core.history import HistoryStore
from picklebot.utils.config import Config


@dataclass
class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
