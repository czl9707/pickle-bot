"""CLI command handlers for pickle-bot."""

from picklebot.core import Agent, SharedContext
from picklebot.core.agent_loader import AgentLoader
from picklebot.provider import LLMProvider
from picklebot.utils.config import Config
from picklebot.frontend import ConsoleFrontend
from picklebot.tools.registry import ToolRegistry


class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

        # Load agent definition
        loader = AgentLoader(config.agents_path, config.llm)
        self.agent_def = loader.load(self.agent_id)

        self.frontend = ConsoleFrontend(self.agent_def)
        self.context = SharedContext(config=config)

        self.agent = Agent(
            agent_def=self.agent_def,
            llm=LLMProvider.from_config(self.agent_def.llm),
            tools=ToolRegistry.with_builtins(),
            context=self.context,
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

                response = await session.chat(user_input, self.frontend)
                self.frontend.show_agent_response(response)

            except KeyboardInterrupt:
                self.frontend.show_system_message(
                    "\n[yellow]Session interrupted.[/yellow]"
                )
                break
            except Exception as e:
                self.frontend.show_system_message(f"[red]Error: {e}[/red]")
