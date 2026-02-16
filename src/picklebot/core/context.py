from picklebot.core.agent_loader import AgentLoader
from picklebot.core.cron_loader import CronLoader
from picklebot.core.history import HistoryStore
from picklebot.core.skill_loader import SkillLoader
from picklebot.utils.config import Config


class SharedContext:
    """Global shared state for the application."""

    config: Config
    history_store: HistoryStore
    agent_loader: AgentLoader
    skill_loader: SkillLoader
    cron_loader: CronLoader

    def __init__(self, config: Config):
        self.config = config
        self.history_store = HistoryStore.from_config(config)
        self.agent_loader = AgentLoader.from_config(config)
        self.skill_loader = SkillLoader.from_config(config)
        self.cron_loader = CronLoader.from_config(config)
