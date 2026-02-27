"""Built-in slash command handlers."""

from picklebot.core.commands.base import Command, CommandResult
from picklebot.core.context import SharedContext


class HelpCommand(Command):
    """Show available commands."""

    name = "help"
    aliases = ["?"]

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        lines = [
            "**Available Commands:**",
            "`/help` - Show this message",
            "`/agent` - List all agents",
            "`/skills` - List all skills",
            "`/crons` - List all cron jobs",
        ]
        return CommandResult(message="\n".join(lines))


class AgentCommand(Command):
    """List all configured agents."""

    name = "agent"
    aliases = ["agents"]

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        agents = ctx.agent_loader.discover_agents()
        if not agents:
            return CommandResult(message="No agents configured.")

        lines = ["**Agents:**"]
        for agent in agents:
            lines.append(f"- `{agent.id}`: {agent.name} ({agent.llm.model})")
        return CommandResult(message="\n".join(lines))


class SkillsCommand(Command):
    """List all configured skills."""

    name = "skills"

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        skills = ctx.skill_loader.discover_skills()
        if not skills:
            return CommandResult(message="No skills configured.")

        lines = ["**Skills:**"]
        for skill in skills:
            lines.append(f"- `{skill.id}`: {skill.name}")
        return CommandResult(message="\n".join(lines))


class CronsCommand(Command):
    """List all configured cron jobs."""

    name = "crons"

    def execute(self, args: str, ctx: SharedContext) -> CommandResult:
        crons = ctx.cron_loader.discover_crons()
        if not crons:
            return CommandResult(message="No cron jobs configured.")

        lines = ["**Cron Jobs:**"]
        for cron in crons:
            lines.append(f"- `{cron.id}`: {cron.schedule}")
        return CommandResult(message="\n".join(lines))
