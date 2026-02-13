"""CLI command handlers for pickle-bot."""

from picklebot.core.agent import Agent
from picklebot.core.history import HistoryStore
from picklebot.config import Config
from picklebot.frontend.console import ConsoleFrontend

class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config):
        """
        Initialize the session.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.frontend = ConsoleFrontend(config)
        history = HistoryStore(base_path=config.workspace / config.history.path)

        self.agent = Agent(
            config, 
            frontend=self.frontend, 
            history=history
        )

    async def run(self) -> None:
        """Run the interactive chat loop."""
        self.frontend.show_welcome()

        # Initialize session for history persistence
        await self.agent.initialize_session()

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
