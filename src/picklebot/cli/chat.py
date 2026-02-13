"""CLI command handlers for pickle-bot."""

from picklebot.core.agent import Agent
from picklebot.config import Config
from picklebot.frontend.console import ConsoleFrontend
from picklebot.tools.builtin_tools import register_builtin_tools
from picklebot.tools.registry import ToolRegistry


class Session:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config):
        """
        Initialize the session.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.frontend = ConsoleFrontend(config)

        registry = ToolRegistry()
        register_builtin_tools(registry)

        # Create agent with tool registry and frontend
        self.agent = Agent(config, tool_registry=registry, frontend=self.frontend)

    async def run(self) -> None:
        """Run the interactive chat loop."""
        self.frontend.show_welcome()

        while True:
            try:
                user_input = self.frontend.get_user_input()

                if user_input.lower() in ["quit", "exit", "q"]:
                    self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Get response from agent
                response = await self.agent.chat(user_input)

                self.frontend.show_agent_response(response)

            except KeyboardInterrupt:
                self.frontend.show_system_message("\n[yellow]Session interrupted.[/yellow]")
                break
            except Exception as e:
                self.frontend.show_system_message(f"[red]Error: {e}[/red]")
