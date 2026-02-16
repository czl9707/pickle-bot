"""Agent definition loader."""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

import yaml

from picklebot.utils.config import Config, LLMConfig


class AgentBehaviorConfig(BaseModel):
    """Agent behavior settings."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)


class AgentDef(BaseModel):
    """Loaded agent definition with merged settings."""

    id: str
    name: str
    system_prompt: str
    llm: LLMConfig
    behavior: AgentBehaviorConfig
    allow_skills: bool = False


class AgentNotFoundError(Exception):
    """Agent folder or AGENT.md doesn't exist."""

    def __init__(self, agent_id: str):
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class InvalidAgentError(Exception):
    """Agent file is malformed."""

    def __init__(self, agent_id: str, reason: str):
        super().__init__(f"Invalid agent '{agent_id}': {reason}")
        self.agent_id = agent_id
        self.reason = reason


class AgentLoader:
    """Loads agent definitions from AGENT.md files."""

    @staticmethod
    def from_config(config: Config) -> "AgentLoader":
        return AgentLoader(config.agents_path, config.llm)

    def __init__(self, agents_path: Path, shared_llm: LLMConfig):
        """
        Initialize AgentLoader.

        Args:
            agents_path: Directory containing agent folders
            shared_llm: Shared LLM config to fall back to
        """
        self.agents_path = agents_path
        self.shared_llm = shared_llm

    def load(self, agent_id: str) -> AgentDef:
        """
        Load agent by ID.

        Args:
            agent_id: Agent folder name

        Returns:
            AgentDef with merged settings

        Raises:
            AgentNotFoundError: Agent folder or file doesn't exist
            InvalidAgentError: Agent file is malformed
        """
        agent_file = self.agents_path / agent_id / "AGENT.md"
        if not agent_file.exists():
            raise AgentNotFoundError(agent_id)

        try:
            frontmatter, body = self._parse_agent_file(agent_file)
        except Exception as e:
            raise InvalidAgentError(agent_id, str(e))

        if "name" not in frontmatter:
            raise InvalidAgentError(agent_id, "missing required field: name")

        merged_llm = self._merge_llm_config(frontmatter)

        return AgentDef(
            id=agent_id,
            name=frontmatter["name"],
            system_prompt=body.strip(),
            llm=merged_llm,
            behavior=AgentBehaviorConfig(
                temperature=frontmatter.get("temperature", 0.7),
                max_tokens=frontmatter.get("max_tokens", 2048),
            ),
        )

    def _parse_agent_file(self, path: Path) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter + markdown body.

        Args:
            path: Path to AGENT.md file

        Returns:
            Tuple of (frontmatter dict, body string)
        """
        content = path.read_text()
        parts = [p for p in content.split("---\n") if p.strip()]

        if len(parts) < 2:
            return {}, content

        frontmatter_text = parts[0]
        body = "---\n".join(parts[1:])

        frontmatter = yaml.safe_load(frontmatter_text) or {}
        return frontmatter, body

    def _merge_llm_config(self, frontmatter: dict[str, Any]) -> LLMConfig:
        """
        Merge agent overrides with shared LLM config.

        Args:
            frontmatter: Parsed frontmatter dict

        Returns:
            LLMConfig with merged settings
        """
        return LLMConfig(
            provider=frontmatter.get("provider", self.shared_llm.provider),
            model=frontmatter.get("model", self.shared_llm.model),
            api_key=frontmatter.get("api_key", self.shared_llm.api_key),
            api_base=frontmatter.get("api_base", self.shared_llm.api_base),
        )
