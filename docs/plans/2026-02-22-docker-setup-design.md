# Docker Setup Design

Containerize pickle-bot server for deployment with persistent workspace storage.

## Requirements

- Run server mode with HTTP API on port 8000
- Persist workspace (agents, skills, crons, configs) across container restarts
- Support Python 3.13 + uv + npm (Node.js)
- Secrets stored in workspace config files (existing behavior)

## Design

### Dockerfile

Single-stage build using `python:3.13-slim`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install Node.js (for future npm needs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Create workspace directory (will be mounted)
RUN mkdir -p /app/workspace

# Expose the API port
EXPOSE 8000

# Set the workspace location
ENV PICKLEBOT_WORKSPACE=/app/workspace

# Run the server
CMD ["uv", "run", "picklebot", "server", "-w", "/app/workspace"]
```

### compose.yaml

```yaml
services:
  picklebot:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ${WORKSPACE_PATH:-./workspace}:/app/workspace
    restart: unless-stopped
```

### .dockerignore

```
.git
.venv
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
.worktrees
*.egg-info
```

## Usage

```bash
# Build and run with default workspace
docker compose up -d

# Or with custom workspace path
WORKSPACE_PATH=/path/to/workspace docker compose up -d

# View logs
docker compose logs -f picklebot

# Stop
docker compose down
```

## Workspace Structure

The mounted workspace contains all persistent data:

```
workspace/
├── config.system.yaml    # System defaults
├── config.user.yaml      # User config + secrets
├── agents/               # Agent definitions
├── skills/               # Skill definitions
├── crons/                # Cron definitions
└── memories/             # Agent memories
```

## Decisions

1. **Single-stage build** - Simpler than multi-stage, adequate for this use case
2. **apt for Node.js** - Standard Debian packages, no extra repos needed
3. **uv from official image** - `COPY --from` is clean and reliable
4. **No dev dependencies** - Keeps image smaller for production
5. **Environment variable for workspace path** - Flexible host mounting via `WORKSPACE_PATH`
