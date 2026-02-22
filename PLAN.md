# Pickle-Bot

A personal AI assistant with pluggable tools and multi-agent support.

## Project Status

**Active Development**

Core features are implemented and production-ready:

- Multi-agent AI with specialized agents (Pickle, Cookie)
- Multiple platforms (CLI, Telegram, Discord)
- HTTP API for SDK-like access
- Scheduled cron jobs
- Long-term memory system
- Extensible tools and skills

## Documentation

- **[Configuration](docs/configuration.md)** - Setup and configuration guide
- **[Features](docs/features.md)** - Agents, skills, crons, memory, messaging, API
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
