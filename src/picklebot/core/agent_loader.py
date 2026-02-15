"""Agent definition loader."""

from pathlib import Path

from picklebot.utils.config import LLMConfig
from picklebot.core.agent_def import AgentDef, AgentBehaviorConfig


class AgentError(Exception):
    """Base error for agent loading."""

    pass


class AgentNotFoundError(AgentError):
    """Agent folder or AGENT.md doesn't exist."""

    def __init__(self, agent_id: str):
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class InvalidAgentError(AgentError):
    """Agent file is malformed."""

    def __init__(self, agent_id: str, reason: str):
        super().__init__(f"Invalid agent '{agent_id}': {reason}")
        self.agent_id = agent_id
        self.reason = reason
