from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from picklebot.server.websocket_worker import WebSocketWorker

from picklebot.core.agent_loader import AgentLoader
from picklebot.core.commands.registry import CommandRegistry
from picklebot.core.cron_loader import CronLoader
from picklebot.core.history import HistoryStore
from picklebot.core.prompt_builder import PromptBuilder
from picklebot.core.routing import RoutingTable
from picklebot.core.skill_loader import SkillLoader
from picklebot.core.eventbus import EventBus
from picklebot.channel.base import Channel
from picklebot.utils.config import Config


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader
    command_registry: CommandRegistry
    channels: list[Channel[Any]]
    eventbus: EventBus
    routing_table: RoutingTable
    prompt_builder: PromptBuilder

    def __init__(
        self, config: Config, channels: list[Channel[Any]] | None = None
    ) -> None:
        self.config = config
        self.history_store = HistoryStore.from_config(config)
        self.agent_loader = AgentLoader.from_config(config)
        self.skill_loader = SkillLoader.from_config(config)
        self.cron_loader = CronLoader.from_config(config)
        self.command_registry = CommandRegistry.with_builtins()

        # Use provided channels (CLI mode) or load from config (server mode)
        if channels is not None:
            self.channels = channels
        else:
            self.channels = Channel.from_config(config)

        self.eventbus = EventBus(self)
        self.routing_table = RoutingTable(self)
        self.prompt_builder = PromptBuilder(self)
        self.websocket_worker: "WebSocketWorker | None" = None
