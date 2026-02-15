"""Agent definition models."""

from pydantic import BaseModel, Field

from picklebot.utils.config import LLMConfig


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
