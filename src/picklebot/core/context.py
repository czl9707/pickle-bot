import asyncio
from typing import TYPE_CHECKING

from picklebot.core.agent_loader import AgentLoader
from picklebot.core.commands.registry import CommandRegistry
from picklebot.core.cron_loader import CronLoader
from picklebot.core.history import HistoryStore
from picklebot.core.skill_loader import SkillLoader
from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import Config

if TYPE_CHECKING:
    from picklebot.server.base import Job


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader
    command_registry: CommandRegistry
    messagebus_buses: list[MessageBus]
    _agent_queue: asyncio.Queue["Job"] | None

    def __init__(self, config: Config):
        self.config = config
        self.history_store = HistoryStore.from_config(config)
        self.agent_loader = AgentLoader.from_config(config)
        self.skill_loader = SkillLoader.from_config(config)
        self.cron_loader = CronLoader.from_config(config)
        self.messagebus_buses = MessageBus.from_config(config)
        self.command_registry = CommandRegistry.with_builtins()
        self._agent_queue = None

    @property
    def agent_queue(self) -> asyncio.Queue["Job"]:
        """Lazily create agent queue on first access."""
        if self._agent_queue is None:
            self._agent_queue = asyncio.Queue()
        return self._agent_queue
