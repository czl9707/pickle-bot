# src/picklebot/core/routing.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from re import Pattern
from typing import TYPE_CHECKING

from picklebot.core.agent import Agent
from picklebot.core.events import EventSource
from picklebot.utils.config import SourceSessionConfig

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


@dataclass
class Binding:
    """A routing binding that matches sources to agents."""

    agent: str
    value: str
    tier: int = field(init=False)
    pattern: Pattern = field(init=False)

    def __post_init__(self):
        self.pattern = re.compile(f"^{self.value}$")
        self.tier = self._compute_tier()

    def _compute_tier(self) -> int:
        """
        Compute specificity tier.

        0 = exact literal (no regex special chars)
        1 = specific regex (anchors, character classes)
        2 = wildcard (. or .*)
        """
        if not any(c in self.value for c in r".*+?[]()|^$"):
            return 0
        if ".*" in self.value:
            return 2
        return 1


@dataclass
class RoutingTable:
    """Routes sources to agents using regex bindings."""

    context: SharedContext
    bindings: list[Binding] | None = field(default=None, init=False)
    _config_hash: int | None = field(default=None, init=False)

    def _load_bindings(self) -> list[Binding]:
        """Load and sort bindings from config. Cached until config changes."""
        bindings_data = self.context.config.routing.get("bindings", [])
        current_hash = hash(tuple((b["agent"], b["value"]) for b in bindings_data))

        if self.bindings is not None and self._config_hash == current_hash:
            return self.bindings

        # Rebuild
        bindings_with_order = [
            (Binding(agent=b["agent"], value=b["value"]), i)
            for i, b in enumerate(bindings_data)
        ]
        bindings_with_order.sort(key=lambda x: (x[0].tier, x[1]))
        self.bindings = [b for b, _ in bindings_with_order]
        self._config_hash = current_hash

        return self.bindings

    def resolve(self, source: str) -> str:
        """Return agent_id for source, falling back to default_agent if no match."""
        for binding in self._load_bindings():
            if binding.pattern.match(source):
                return binding.agent
        return self.context.config.default_agent

    def get_or_create_session_id(self, source: EventSource) -> str:
        """Get existing or create new session_id for source.

        For existing sessions, returns cached session_id (session affinity).
        For new sessions, resolves agent from routing table.

        Args:
            source: Typed EventSource object

        Returns:
            session_id: Existing or newly created session identifier
        """
        source_str = str(source)

        source_session = self.context.config.sources.get(source_str)
        if source_session:
            return source_session.session_id

        agent_id = self.resolve(source_str)
        agent_def = self.context.agent_loader.load(agent_id)
        agent = Agent(agent_def, self.context)
        session = agent.new_session(source)

        # Cache the session
        self.context.config.set_runtime(
            f"sources.{source_str}", SourceSessionConfig(session_id=session.session_id)
        )

        return session.session_id

    def persist_binding(self, source_pattern: str, agent_id: str) -> None:
        """
        Add and persist a routing binding to config.user.yaml.

        Args:
            source_pattern: Source pattern to match
            agent_id: Agent to route to
        """
        bindings = self.context.config.routing.get("bindings", [])
        bindings.append({"agent": agent_id, "value": source_pattern})
        self.context.config.set_runtime("routing.bindings", bindings)

    def config_source_session_cache(
        self, source_str: str, session_id: str | None
    ) -> None:
        """
        Clear session cache for a source.

        Args:
            source_str: Source string to clear
        """
        if session_id is None:
            if source_str in self.context.config.sources:
                del self.context.config.sources[source_str]
                self.context.config.set_runtime(
                    "sources", self.context.config.sources
                )
        else:
            self.context.config.set_runtime(
                f"""sources.{source_str}""", SourceSessionConfig(session_id=session_id)
            )
