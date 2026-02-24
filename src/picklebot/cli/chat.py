"""Chat CLI command for interactive sessions."""

import asyncio

import typer

from picklebot.core import Agent, SharedContext
from picklebot.core.agent import SessionMode
from picklebot.frontend import ConsoleFrontend
from picklebot.server.agent_worker import AgentDispatcherWorker
from picklebot.utils.config import Config
from picklebot.utils.logging import setup_logging


class ChatLoop:
    """Interactive chat session with the agent."""

    def __init__(self, config: Config, agent_id: str | None = None):
        self.config = config
        self.agent_id = agent_id or config.default_agent

        self.context = SharedContext(config=config)
        self.dispatcher = AgentDispatcherWorker(self.context)

        self.agent_def = self.context.agent_loader.load(self.agent_id)
        self.frontend = ConsoleFrontend(self.agent_def)
        self.agent = Agent(agent_def=self.agent_def, context=self.context)

        setup_logging(config, console_output=False)

    async def run(self) -> None:
        """Run the interactive chat loop."""
        # Start dispatcher in background to process subagent dispatches
        dispatcher_task = asyncio.create_task(self.dispatcher.run())

        session = self.agent.new_session(SessionMode.CHAT)
        await self.frontend.show_welcome()

        try:
            while True:
                try:
                    user_input = self.frontend.console.input(
                        "[bold green]You:[/bold green] "
                    )

                    if user_input.lower() in ["quit", "exit", "q"]:
                        await self.frontend.show_system_message(
                            "[yellow]Goodbye![/yellow]"
                        )
                        break

                    if not user_input.strip():
                        continue

                    await session.chat(user_input, self.frontend)

                except KeyboardInterrupt:
                    await self.frontend.show_system_message(
                        "\n[yellow]Session interrupted.[/yellow]"
                    )
                    break
                except Exception as e:
                    await self.frontend.show_system_message(f"[red]Error: {e}[/red]")
        finally:
            # Clean up dispatcher
            dispatcher_task.cancel()
            try:
                await dispatcher_task
            except asyncio.CancelledError:
                pass


def chat_command(ctx: typer.Context, agent_id: str | None = None) -> None:
    """Start interactive chat session."""
    config = ctx.obj.get("config")

    setup_logging(config, console_output=False)

    chat_loop = ChatLoop(config, agent_id=agent_id)
    asyncio.run(chat_loop.run())
