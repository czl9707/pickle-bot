from picklebot.core.history import HistoryStore
from picklebot.utils.config import Config


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore

    def __init__(self, config: Config):
        self.config = config
        self.history_store = HistoryStore.from_config(config)