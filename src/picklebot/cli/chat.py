"""CLI command handlers for pickle-bot."""

from picklebot.core import Agent, SharedContext
from picklebot.core.agent import SessionMode
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend
from picklebot.utils.logging import setup_logging


class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

        self.context = SharedContext(config=config)

        self.agent_def = self.context.agent_loader.load(self.agent_id)
        self.frontend = ConsoleFrontend(self.agent_def)
        self.agent = Agent(agent_def=self.agent_def, context=self.context)

        setup_logging(config, console_output=False)

    async def run(self) -> None:
        """Run the interactive chat loop."""
        session = self.agent.new_session(SessionMode.CHAT)
        await self.frontend.show_welcome()

        while True:
            try:
                user_input = self.frontend.console.input(
                    "[bold green]You:[/bold green] "
                )

                if user_input.lower() in ["quit", "exit", "q"]:
                    await self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                # Show user message (raw, no agent_id)
                await self.frontend.show_message(
                    f"[bold green]You:[/bold green] {user_input}"
                )

                # Get response (chat() calls show_message internally)
                await session.chat(user_input, self.frontend)

            except KeyboardInterrupt:
                await self.frontend.show_system_message(
                    "\n[yellow]Session interrupted.[/yellow]"
                )
                break
            except Exception as e:
                await self.frontend.show_system_message(f"[red]Error: {e}[/red]")
