"""CLI command handlers for pickle-bot."""

from picklebot.core import Agent, Session, HistoryStore, SharedContext
from picklebot.provider import LLMProvider
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend
from picklebot.tools.registry import ToolRegistry


class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config):
        self.config = config
        self.frontend = ConsoleFrontend(config.agent)

        # Shared layer
        self.context = SharedContext(
            config=config,
            history_store=HistoryStore.from_config(config)
        )

        # Agent (reusable, created once)
        self.agent = Agent(
            agent_config=config.agent,
            llm=LLMProvider.from_config(config.llm),
            tools=ToolRegistry.with_builtins(),
            context=self.context
        )

    async def run(self) -> None:
        """Run the interactive chat loop."""
        session = self.agent.new_session()
        self.frontend.show_welcome()

        while True:
            try:
                user_input = self.frontend.get_user_input()

                if user_input.lower() in ["quit", "exit", "q"]:
                    self.frontend.show_system_message("[yellow]Goodbye![/yellow]")
                    break

                if not user_input.strip():
                    continue

                response = await self.agent.chat(session, user_input, self.frontend)
                self.frontend.show_agent_response(response)

            except KeyboardInterrupt:
                self.frontend.show_system_message("\n[yellow]Session interrupted.[/yellow]")
                break
            except Exception as e:
                self.frontend.show_system_message(f"[red]Error: {e}[/red]")
