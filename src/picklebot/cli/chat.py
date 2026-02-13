"""CLI command handlers for pickle-bot."""

from picklebot.core import Agent, AgentSession, HistoryStore
from picklebot.provider import LLMProvider
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend

class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config):
        """
        Initialize the session.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.frontend = ConsoleFrontend(config.agent)
        self.history_store=HistoryStore.from_config(config)
        


    async def run(self) -> None:
        """Run the interactive chat loop."""

        async with AgentSession(self.config.agent, self.history_store) as session:
            self.agent = Agent(
                config=self.config.agent, 
                frontend=self.frontend, 
                session=session,
                llm_provider=LLMProvider.from_config(self.config.llm)
            )
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
