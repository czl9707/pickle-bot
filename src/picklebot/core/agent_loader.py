"""Agent definition loader."""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from picklebot.utils.config import Config, LLMConfig
from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    parse_definition,
)


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
            DefNotFoundError: Agent folder or file doesn't exist
            InvalidDefError: Agent file is malformed
        """
        agent_file = self.agents_path / agent_id / "AGENT.md"
        if not agent_file.exists():
            raise DefNotFoundError("agent", agent_id)

        try:
            content = agent_file.read_text()
            agent_def = parse_definition(content, agent_id, self._parse_agent_def)
        except InvalidDefError:
            raise
        except Exception as e:
            raise InvalidDefError("agent", agent_id, str(e))

        return agent_def

    def _parse_agent_def(
        self, def_id: str, frontmatter: dict[str, Any], body: str
    ) -> AgentDef:
        """Parse agent definition from frontmatter (callback for parse_definition)."""
        if "name" not in frontmatter:
            raise InvalidDefError("agent", def_id, "missing required field: name")

        merged_llm = self._merge_llm_config(frontmatter)

        return AgentDef(
            id=def_id,
            name=frontmatter["name"],
            system_prompt=body.strip(),
            llm=merged_llm,
            behavior=AgentBehaviorConfig(
                temperature=frontmatter.get("temperature", 0.7),
                max_tokens=frontmatter.get("max_tokens", 2048),
            ),
            allow_skills=frontmatter.get("allow_skills", False),
        )

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
