"""Prompt builder that assembles system prompt from layers."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from picklebot.core.cron_loader import CronLoader
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

    def __init__(self, workspace_path: Path, cron_loader: "CronLoader"):
        self.workspace_path = workspace_path
        self.cron_loader = cron_loader

    def build(self, session) -> str:
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

        # BOOTSTRAP.md
        bootstrap_path = self.workspace_path / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            parts.append(bootstrap_path.read_text().strip())

        # AGENTS.md
        agents_path = self.workspace_path / "AGENTS.md"
        if agents_path.exists():
            parts.append(agents_path.read_text().strip())

        # Dynamic cron list
        cron_list = self._format_cron_list()
        if cron_list:
            parts.append(cron_list)

        return "\n\n".join(parts)

    def _format_cron_list(self) -> str:
        """Format crons as markdown list."""
        crons = self.cron_loader.discover_crons()
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
            platform = "cron"
        else:
            platform = source.platform_name or "unknown"
        return f"You are responding via {platform}."
