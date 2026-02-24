# Pickle-Bot

Build your own AI companion. Name it. Talk to it. Teach it things.

Pickle-bot is a framework for creating personal AI assistants - the kind you can chat with, assign tasks to, and watch grow smarter over time. Pickle and Cookie started as cats in my life, and now they're AI agents who help me every day.

## Installation

```bash
# From PyPI
pip install pickle-bot

# Or from source
git clone https://github.com/zane-chen/pickle-bot.git
cd pickle-bot
uv sync
```

## Quick Start

```bash
picklebot init      # First run: meet your new companion
picklebot chat      # Start chatting
picklebot server    # Run background tasks (crons, Telegram, Discord)
```

The first run guides you through setup. Pick your LLM, configure your agent, and you're ready.

## Features

- **Multi-Agent AI** - Create specialized agents for different tasks (Pickle for general chat, Cookie for memories, or build your own)
- **Web Tools** - Search the web, read pages, do research
- **Skills** - Teach your agent new tricks by writing markdown files
- **Cron Jobs** - Schedule recurring tasks and reminders
- **Memory System** - Your agent remembers things across conversations
- **Multi-Platform** - CLI, Telegram, Discord - same agent, different places
- **HTTP API** - Hook your agent into other apps

## The Pets

Pickle and Cookie are cats. There's a puppy coming soon. The point is: these are companions, not tools. You name them, you teach them, you talk to them. They remember what matters and help with what you need.

Create your own agents by dropping a file in `agents/{name}/AGENT.md`. Give them a personality. Give them skills. See what happens.

## Documentation

- **[Configuration](docs/configuration.md)** - Full config reference
- **[Features](docs/features.md)** - How to use each feature
- **[Architecture](docs/architecture.md)** - How it works under the hood

## Development

```bash
uv run pytest           # Run tests
uv run black .          # Format code
uv run ruff check .     # Lint
```

## Docker

```bash
docker compose up -d
docker compose logs -f picklebot
```

## License

MIT
