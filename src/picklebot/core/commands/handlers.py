"""Built-in slash command handlers."""

from typing import TYPE_CHECKING

from picklebot.core.commands.base import Command

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession


class HelpCommand(Command):
    """Show available commands."""

    name = "help"
    aliases = ["?"]
    description = "Show available commands"

    def execute(self, args: str, session: "AgentSession") -> str:
        lines = ["**Available Commands:**"]
        for cmd in session.shared_context.command_registry.list_commands():
            names = [f"/{cmd.name}"] + [f"/{a}" for a in cmd.aliases]
            lines.append(f"{', '.join(names)} - {cmd.description}")
        return "\n".join(lines)


class AgentCommand(Command):
    """List agents or switch agent."""

    name = "agent"
    aliases = ["agents"]
    description = "Switch to a different agent (starts fresh session)"

    def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            # List agents
            agents = session.shared_context.agent_loader.discover_agents()
            lines = ["**Agents:**"]
            for agent in agents:
                marker = " (current)" if agent.id == session.agent.agent_def.id else ""
                lines.append(f"- `{agent.id}`: {agent.name}{marker}")
            return "\n".join(lines)

        # Switch agent
        agent_id = args.strip()
        source_str = str(session.source)

        # Verify agent exists
        try:
            session.shared_context.agent_loader.load(agent_id)
        except ValueError:
            return f"✗ Agent `{agent_id}` not found."

        # Add runtime binding + clear cache
        routing = session.shared_context.routing_table
        routing.add_runtime_binding(source_str, agent_id)
        routing.clear_session_cache(source_str)

        return f"✓ Switched to `{agent_id}`. Next message starts fresh conversation."


class SkillsCommand(Command):
    """List all skills."""

    name = "skills"
    description = "List all skills"

    def execute(self, args: str, session: "AgentSession") -> str:
        skills = session.shared_context.skill_loader.discover_skills()
        if not skills:
            return "No skills configured."

        lines = ["**Skills:**"]
        for skill in skills:
            lines.append(f"- `{skill.id}`: {skill.description}")
        return "\n".join(lines)


class CronsCommand(Command):
    """List all cron jobs."""

    name = "crons"
    description = "List all cron jobs"

    def execute(self, args: str, session: "AgentSession") -> str:
        crons = session.shared_context.cron_loader.discover_crons()
        if not crons:
            return "No cron jobs configured."

        lines = ["**Cron Jobs:**"]
        for cron in crons:
            lines.append(f"- `{cron.id}`: {cron.schedule}")
        return "\n".join(lines)
