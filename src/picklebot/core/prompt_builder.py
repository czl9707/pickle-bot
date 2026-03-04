"""Prompt builder that assembles system prompt from layers."""

from datetime import datetime
from typing import TYPE_CHECKING

from picklebot.utils.def_loader import get_template_variables, substitute_template


if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession
    from picklebot.core.context import SharedContext
    from picklebot.core.events import EventSource


class PromptBuilder:
    """Assembles system prompt from layered sources.

    Layers (in order):
    1. Identity - AGENT.md body (agent_md)
    2. Soul - SOUL.md (personality, optional)
    3. Bootstrap - BOOTSTRAP.md + AGENTS.md + cron list
    4. Runtime - Agent ID + timestamp
    5. Channel - Platform name hint
    """

    def __init__(self, context: "SharedContext"):
        self.context = context

    def build(self, session: "AgentSession") -> str:
        """Build the full system prompt from layers.

        Args:
            session: AgentSession with agent_def and source

        Returns:
            Assembled system prompt string
        """
        layers = []

        # Layer 1: Identity
        layers.append(session.agent.agent_def.agent_md)

        # Layer 2: Soul (optional)
        if session.agent.agent_def.soul_md:
            layers.append(f"## Personality\n\n{session.agent.agent_def.soul_md}")

        # Layer 3: Bootstrap context
        bootstrap = self._load_bootstrap_context()
        if bootstrap:
            layers.append(bootstrap)

        # Layer 4: Runtime context
        layers.append(
            self._build_runtime_context(
                session.agent.agent_def.id,
                datetime.now(),
            )
        )

        # Layer 5: Channel hint
        layers.append(self._build_channel_hint(session.source))

        return "\n\n".join(layers)

    def _load_bootstrap_context(self) -> str:
        """Load BOOTSTRAP.md + AGENTS.md + cron list."""
        parts = []

        bootstrap_path = self.context.config.workspace / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            bootstrap_md = substitute_template(
                bootstrap_path.read_text().strip(),
                get_template_variables(self.context.config),
            )
            parts.append(bootstrap_md)

        agents_path = self.context.config.workspace / "AGENTS.md"
        if agents_path.exists():
            agents_md = substitute_template(
                agents_path.read_text().strip(),
                get_template_variables(self.context.config),
            )
            parts.append(agents_md)

        # Dynamic cron list
        cron_list = self._format_cron_list()
        if cron_list:
            parts.append(cron_list)

        return "\n\n".join(parts)

    def _format_cron_list(self) -> str:
        """Format crons as markdown list."""
        crons = self.context.cron_loader.discover_crons()
        if not crons:
            return ""

        lines = ["## Scheduled Tasks\n"]
        for cron in crons:
            lines.append(f"- **{cron.name}**: {cron.description}")
        return "\n".join(lines)

    def _build_runtime_context(self, agent_id: str, timestamp: datetime) -> str:
        """Build runtime info section."""
        return f"## Runtime\n\nAgent: {agent_id}\nTime: {timestamp.isoformat()}"

    def _build_channel_hint(self, source: "EventSource") -> str:
        """Build platform hint."""
        if source.is_cron:
            return "You are running as a background cron job. Your response will not be sent to user directly."
        if source.is_agent:
            return "You are running as a dispatched subagent. Your response will be sent to main agent."
        elif source.is_platform:
            return f"You are responding via {source.platform_name}."
        else:
            raise ValueError(f"Unknown source type: {source}")
