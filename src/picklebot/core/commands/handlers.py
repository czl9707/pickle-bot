"""Built-in slash command handlers."""

import re
from typing import TYPE_CHECKING

from picklebot.core.commands.base import Command
from picklebot.utils.def_loader import DefNotFoundError

if TYPE_CHECKING:
    from picklebot.core.agent import AgentSession


class CompactCommand(Command):
    """Trigger manual context compaction."""

    name = "compact"
    description = "Compact conversation context manually"

    async def execute(self, args: str, session: "AgentSession") -> str:
        session.state = await session.context_guard.compact_and_roll(session.state)
        msg_count = len(session.state.messages)
        return f"✓ Context compacted. {msg_count} messages retained."


class ContextCommand(Command):
    """Show session context information."""

    name = "context"
    description = "Show session context information"

    async def execute(self, args: str, session: "AgentSession") -> str:
        lines = [
            f"**Messages:** {len(session.state.messages)}",
            f"**Tokens:** {session.context_guard.estimate_tokens(session.state) / session.context_guard.token_threshold}",
        ]
        return "\n".join(lines)


class ClearCommand(Command):
    """Clear conversation and start fresh."""

    name = "clear"
    description = "Clear conversation and start fresh"

    async def execute(self, args: str, session: "AgentSession") -> str:
        # Clear session cache
        source_str = str(session.source)
        session.shared_context.routing_table.clear_session_cache(source_str)

        return "✓ Conversation cleared. Next message starts fresh."


class SessionCommand(Command):
    """Show current session details."""

    name = "session"
    description = "Show current session details"

    async def execute(self, args: str, session: "AgentSession") -> str:
        info = session.shared_context.history_store.get_session_info(session.session_id)

        # Handle case where session not found in index
        created_str = info.created_at if info else "Unknown"

        lines = [
            f"**Session ID:** `{session.session_id}`",
            f"**Agent:** {session.agent.agent_def.name} (`{session.agent.agent_def.id}`)",
            f"**Created:** {created_str}",
            f"**Messages:** {len(session.state.messages)}",
            f"**Source:** `{session.source}`",
        ]
        return "\n".join(lines)


class HelpCommand(Command):
    """Show available commands."""

    name = "help"
    aliases = ["?"]
    description = "Show available commands"

    async def execute(self, args: str, session: "AgentSession") -> str:
        lines = ["**Available Commands:**"]
        for cmd in session.shared_context.command_registry.list_commands():
            names = [f"/{cmd.name}"] + [f"/{a}" for a in cmd.aliases]
            lines.append(f"{', '.join(names)} - {cmd.description}")
        return "\n".join(lines)


class AgentCommand(Command):
    """List agents or show agent details."""

    name = "agent"
    aliases = ["agents"]
    description = "List agents or show agent details"

    async def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            # List agents
            agents = session.shared_context.agent_loader.discover_agents()
            lines = ["**Agents:**"]
            for agent in agents:
                marker = " (current)" if agent.id == session.agent.agent_def.id else ""
                lines.append(f"- `{agent.id}`: {agent.name}{marker}")
            return "\n".join(lines)

        # Show specific agent details
        agent_id = args.strip()
        try:
            agent_def = session.shared_context.agent_loader.load(agent_id)
        except ValueError:
            return f"✗ Agent `{agent_id}` not found."

        lines = [
            f"**Agent:** `{agent_def.id}`",
            f"**Name:** {agent_def.name}",
            f"**Description:** {agent_def.description}",
            f"**LLM:** {agent_def.llm.model}",
        ]

        # Add content sections
        lines.append(f"\n---\n\n**AGENT.md:**\n```\n{agent_def.agent_md}\n```")

        if agent_def.soul_md:
            lines.append(f"\n**SOUL.md:**\n```\n{agent_def.soul_md}\n```")

        return "\n".join(lines)


class SkillsCommand(Command):
    """List all skills or show skill details."""

    name = "skills"
    description = "List all skills or show skill details"

    async def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            skills = session.shared_context.skill_loader.discover_skills()
            if not skills:
                return "No skills configured."

            lines = ["**Skills:**"]
            for skill in skills:
                lines.append(f"- `{skill.id}`: {skill.description}")
            return "\n".join(lines)

        # Show specific skill details
        skill_id = args.strip()
        try:
            skill = session.shared_context.skill_loader.load_skill(skill_id)
        except DefNotFoundError:
            return f"✗ Skill `{skill_id}` not found."

        lines = [
            f"**Skill:** `{skill.id}`",
            f"**Name:** {skill.name}",
            f"**Description:** {skill.description}",
            f"\n---\n\n**SKILL.md:**\n```\n{skill.content}\n```",
        ]
        return "\n".join(lines)


class CronsCommand(Command):
    """List all cron jobs or show cron details."""

    name = "crons"
    description = "List all cron jobs or show cron details"

    async def execute(self, args: str, session: "AgentSession") -> str:
        if not args:
            crons = session.shared_context.cron_loader.discover_crons()
            if not crons:
                return "No cron jobs configured."

            lines = ["**Cron Jobs:**"]
            for cron in crons:
                lines.append(f"- `{cron.id}`: {cron.schedule}")
            return "\n".join(lines)

        # Show specific cron details
        cron_id = args.strip()
        try:
            cron = session.shared_context.cron_loader.load(cron_id)
        except DefNotFoundError:
            return f"✗ Cron `{cron_id}` not found."

        lines = [
            f"**Cron:** `{cron.id}`",
            f"**Name:** {cron.name}",
            f"**Schedule:** `{cron.schedule}`",
            f"**Agent:** {cron.agent}",
            f"\n---\n\n**CRON.md:**\n```\n{cron.prompt}\n```",
        ]
        return "\n".join(lines)


class RouteCommand(Command):
    """Create a routing binding."""

    name = "route"
    description = "Create a routing binding (persists to config)"

    async def execute(self, args: str, session: "AgentSession") -> str:
        parts = args.strip().split(None, 1)
        if len(parts) != 2:
            return "**Usage:** `/route <source_pattern> <agent_id>`\n\nExample: `/route platform-telegram:.* pickle`"

        pattern, agent_id = parts

        # Validate regex pattern
        try:
            re.compile(f"^{pattern}$")
        except re.error as e:
            return f"✗ Invalid regex pattern: {e}"

        # Verify agent exists
        try:
            session.shared_context.agent_loader.load(agent_id)
        except ValueError:
            return f"✗ Agent `{agent_id}` not found."

        # Create and persist binding
        session.shared_context.routing_table.persist_binding(pattern, agent_id)

        return f"✓ Route bound: `{pattern}` → `{agent_id}`"


class BindingsCommand(Command):
    """Show all routing bindings."""

    name = "bindings"
    description = "Show all routing bindings"

    async def execute(self, args: str, session: "AgentSession") -> str:
        bindings = session.shared_context.config.routing.get("bindings", [])

        if not bindings:
            return "No routing bindings configured."

        lines = ["**Routing Bindings:**"]
        for binding in bindings:
            lines.append(f"- `{binding['value']}` → `{binding['agent']}`")

        return "\n".join(lines)
