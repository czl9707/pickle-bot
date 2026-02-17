from picklebot.core.agent_loader import AgentLoader
from picklebot.core.cron_loader import CronLoader
from picklebot.core.history import HistoryStore
from picklebot.core.skill_loader import SkillLoader
from picklebot.messagebus.base import MessageBus
from picklebot.messagebus.telegram_bus import TelegramBus
from picklebot.messagebus.discord_bus import DiscordBus
from picklebot.utils.config import Config


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader
    _messagebus_buses: list[MessageBus] | None = None

    def __init__(self, config: Config):
        self.config = config
        self.history_store = HistoryStore.from_config(config)
        self.agent_loader = AgentLoader.from_config(config)
        self.skill_loader = SkillLoader.from_config(config)
        self.cron_loader = CronLoader.from_config(config)

    @property
    def messagebus_buses(self) -> list[MessageBus]:
        """
        Get list of configured message bus instances.

        Lazily initialized on first access.

        Returns:
            List of MessageBus instances (may be empty)
        """
        if self._messagebus_buses is None:
            self._messagebus_buses = self._create_messagebus_buses()
        return self._messagebus_buses

    def _create_messagebus_buses(self) -> list[MessageBus]:
        """
        Create message bus instances based on configuration.

        Returns:
            List of configured message bus instances
        """
        buses = []

        if self.config.messagebus.telegram and self.config.messagebus.telegram.enabled:
            buses.append(TelegramBus(self.config.messagebus.telegram))

        if self.config.messagebus.discord and self.config.messagebus.discord.enabled:
            buses.append(DiscordBus(self.config.messagebus.discord))

        return buses
