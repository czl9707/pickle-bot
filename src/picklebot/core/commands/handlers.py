"""Built-in slash command handlers."""

from picklebot.core.commands.base import Command
from picklebot.core.context import SharedContext


class HelpCommand(Command):
    """Show available commands."""

    name = "help"
    aliases = ["?"]
    description = "Show available commands"

    def execute(self, args: str, ctx: SharedContext) -> str:
        lines = ["**Available Commands:**"]
        for cmd in ctx.command_registry.list_commands():
            # Format: `/name, /alias1, /alias2` - description
            names = [f"/{cmd.name}"] + [f"/{a}" for a in cmd.aliases]
            lines.append(f"{', '.join(names)} - {cmd.description}")
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
