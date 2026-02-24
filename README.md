# Pickle-Bot

A personal AI assistant framework with multi-agent support, pluggable skills, and web capabilities.

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
picklebot init      # First run: interactive onboarding wizard
picklebot chat      # Start chatting with your AI assistant
```

The first run will guide you through setup with an interactive wizard.

## Features

- **Multi-Agent AI** - Specialized agents with configurable LLM settings
- **Web Tools** - Search and read web content (Brave Search, Crawl4AI)
- **Skills** - On-demand capability loading for complex workflows
- **Cron Jobs** - Scheduled automated tasks
- **Memory System** - Long-term context storage
- **Multi-Platform** - CLI, Telegram, Discord support
- **HTTP API** - RESTful API for programmatic access

## Documentation

- **[Configuration](docs/configuration.md)** - Setup and configuration guide
- **[Features](docs/features.md)** - Agents, skills, crons, memory, web tools
- **[Architecture](docs/architecture.md)** - Technical architecture details

## Development

```bash
uv run pytest           # Run tests
uv run black .          # Format code
uv run ruff check .     # Lint
```

## Docker

Run pickle-bot in a container:

```bash
# Build and run with default workspace
docker compose up -d

# Or specify custom workspace path
WORKSPACE_PATH=/path/to/workspace docker compose up -d

# View logs
docker compose logs -f picklebot

# Stop
docker compose down
```

The workspace directory contains all persistent data (agents, skills, crons, config).

## License

MIT
