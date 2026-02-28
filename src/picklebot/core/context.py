import asyncio
from typing import Any

from picklebot.core.agent_loader import AgentLoader
from picklebot.core.commands.registry import CommandRegistry
from picklebot.core.cron_loader import CronLoader
from picklebot.core.history import HistoryStore
from picklebot.core.skill_loader import SkillLoader
from picklebot.events.bus import EventBus
from picklebot.messagebus.base import MessageBus
from picklebot.utils.config import Config


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader
    command_registry: CommandRegistry
    messagebus_buses: list[MessageBus[Any]]
    eventbus: EventBus
    # Futures for pending jobs (keyed by job_id)
    _pending_futures: dict[str, asyncio.Future[str]]

    def __init__(
        self, config: Config, buses: list[MessageBus[Any]] | None = None
    ) -> None:
        self.config = config
        self.history_store = HistoryStore.from_config(config)
        self.agent_loader = AgentLoader.from_config(config)
        self.skill_loader = SkillLoader.from_config(config)
        self.cron_loader = CronLoader.from_config(config)
        self.command_registry = CommandRegistry.with_builtins()

        # Use provided buses (CLI mode) or load from config (server mode)
        if buses is not None:
            self.messagebus_buses = buses
        else:
            self.messagebus_buses = MessageBus.from_config(config)

        self.eventbus = EventBus()
        self._pending_futures = {}

    def register_future(self, job_id: str, future: asyncio.Future[str]) -> None:
        """Register a future for a pending job."""
        self._pending_futures[job_id] = future

    def get_future(self, job_id: str) -> asyncio.Future[str] | None:
        """Get and remove a future for a completed job."""
        return self._pending_futures.pop(job_id, None)
