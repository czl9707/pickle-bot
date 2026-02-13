import uuid
from dataclasses import dataclass

from picklebot.core.context import SharedContext
from picklebot.core.session import Session
from picklebot.provider import LLMProvider
from picklebot.tools.registry import ToolRegistry
from picklebot.utils.config import AgentConfig


@dataclass
class Agent:
    """
    A configured agent that creates and manages conversation sessions.

    Agent is a factory for sessions and holds the LLM, tools, and config
    that sessions use for chatting.
    """

    agent_config: AgentConfig
    llm: LLMProvider
    tools: ToolRegistry
    context: SharedContext

    def new_session(self) -> Session:
        """
        Create a new conversation session.

        Returns:
            A new Session instance with self as the agent reference.
        """
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            agent_id=self.agent_config.name,
            history_store=self.context.history_store,
            agent=self,
        )
        # Create session in history store
        self.context.history_store.create_session(self.agent_config.name, session_id)
        return session
