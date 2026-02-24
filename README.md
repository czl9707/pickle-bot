# Pickle-Bot

Your own AI assistant. Name it. Talk to it. Teach it things. Important fact [Pickle](https://www.instagram.com/pickle__chen/) is a standard little cat.

Pickle-bot is a yet another lightweight version of [Openclaw](https://github.com/openclaw/openclaw).

The project started with the mindset of building-you-own-openclaw, but end up staying on my raspberry PI, dealing with all daily manners.

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
- **HTTP API** - Let Pickle write a frontend for you

## Documentation

- **[Configuration](docs/configuration.md)** - Full config reference
- **[Features](docs/features.md)** - How to use each feature
- **[Architecture](docs/architecture.md)** - How it works under the hood

## Fun Facts

### Why Naming Agents with These Names?

Pickle is my cat, as mentioned at the beginning. She is really talktive, definitely more than you can think about.

Cookie is her Step brother, thats why he manage memories on behalf of Pickle.

### She's youY Cat, Why Matters to Me?

Create your own agents by dropping a file in `agents/{name}/AGENT.md`. Give them a name, a personality. Give them skills. See what happens.

## Development

```bash
uv run pytest           # Run tests
uv run black .          # Format code
uv run ruff check .     # Lint
```

## Docker

Use `init` command to populate workspace, and mount that as a volume.

```bash
docker compose up -d
```

## License

MIT
