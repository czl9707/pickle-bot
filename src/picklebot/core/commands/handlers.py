"""Built-in slash command handlers."""

from typing import TYPE_CHECKING

from picklebot.core.commands.base import Command
from picklebot.core.context import SharedContext

if TYPE_CHECKING:
    from picklebot.core.commands.registry import CommandRegistry


class HelpCommand(Command):
    """Show available commands."""

    name = "help"
    aliases = ["?"]
    description = "Show available commands"
    _registry: "CommandRegistry | None" = None

    def set_registry(self, registry: "CommandRegistry") -> None:
        """Set the registry reference for dynamic help generation."""
        self._registry = registry

    def execute(self, args: str, ctx: SharedContext) -> str:
        if self._registry is None:
            return "Help unavailable: registry not set."

        lines = ["**Available Commands:**"]
        # Get unique commands (by name, not aliases)
        seen = set()
        for cmd in self._registry.list_commands():
            if cmd.name not in seen:
                seen.add(cmd.name)
                lines.append(f"`/{cmd.name}` - {cmd.description}")
        return "\n".join(lines)


class AgentCommand(Command):
    """List all configured agents."""

    name = "agent"
    aliases = ["agents"]
    description = "List all agents"

    def execute(self, args: str, ctx: SharedContext) -> str:
        agents = ctx.agent_loader.discover_agents()
        if not agents:
            return "No agents configured."

        lines = ["**Agents:**"]
        for agent in agents:
            lines.append(f"- `{agent.id}`: {agent.name} ({agent.llm.model})")
        return "\n".join(lines)


class SkillsCommand(Command):
    """List all configured skills."""

    name = "skills"
    description = "List all skills"

    def execute(self, args: str, ctx: SharedContext) -> str:
        skills = ctx.skill_loader.discover_skills()
        if not skills:
            return "No skills configured."

        lines = ["**Skills:**"]
        for skill in skills:
            lines.append(f"- `{skill.id}`: {skill.name}")
        return "\n".join(lines)


class CronsCommand(Command):
    """List all configured cron jobs."""

    name = "crons"
    description = "List all cron jobs"

    def execute(self, args: str, ctx: SharedContext) -> str:
        crons = ctx.cron_loader.discover_crons()
        if not crons:
            return "No cron jobs configured."

        lines = ["**Cron Jobs:**"]
        for cron in crons:
            lines.append(f"- `{cron.id}`: {cron.schedule}")
        return "\n".join(lines)
