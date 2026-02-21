# Pickle-Bot

A personal AI assistant with pluggable tools and multi-agent support.

## Quick Start

```bash
git clone <repo-url>
cd pickle-bot
uv sync
uv run picklebot chat
```

## What It Does

- **Multi-Agent AI** - Specialized agents (Pickle for general tasks, Cookie for memory)
- **Multiple Platforms** - Chat via CLI, Telegram, or Discord
- **Scheduled Tasks** - Run cron jobs automatically in server mode
- **Long-Term Memory** - Persistent context across conversations
- **Extensible** - Add custom tools, skills, and agents

## Documentation

- **[Configuration](docs/configuration.md)** - Setup and configuration guide
- **[Features](docs/features.md)** - Agents, skills, crons, memory, and messaging
- **[Architecture](docs/architecture.md)** - Technical architecture details
- **[Extending](docs/extending.md)** - How to add tools, providers, and agents

## Development

```bash
uv run pytest           # Run tests
uv run black .          # Format code
uv run ruff check .     # Lint
```

## License

MIT
