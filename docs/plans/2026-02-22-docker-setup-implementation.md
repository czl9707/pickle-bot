# Docker Setup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Containerize pickle-bot server with persistent workspace storage.

**Architecture:** Single-stage Docker build using python:3.13-slim, with uv for dependency management and Node.js for future npm needs. Workspace mounted via Docker Compose volume.

**Tech Stack:** Docker, Docker Compose, Python 3.13, uv, Node.js

---

### Task 1: Create .dockerignore

**Files:**
- Create: `.dockerignore`

**Step 1: Create .dockerignore**

```dockerignore
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

**Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore for Docker builds"
```

---

### Task 2: Create Dockerfile

**Files:**
- Create: `Dockerfile`

**Step 1: Create Dockerfile**

```dockerfile
# Use Python 3.13 slim as base
FROM python:3.13-slim

# Set working directory
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

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile for containerized server"
```

---

### Task 3: Create compose.yaml

**Files:**
- Create: `compose.yaml`

**Step 1: Create compose.yaml**

```yaml
services:
  picklebot:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ${WORKSPACE_PATH:-~/.pickle-bot}:/app/workspace
    restart: unless-stopped
```

**Step 2: Commit**

```bash
git add compose.yaml
git commit -m "feat: add compose.yaml for Docker deployment"
```

---

### Task 4: Verify Docker build

**Step 1: Build the image**

```bash
docker build -t picklebot:test .
```

Expected: Build succeeds without errors

**Step 2: Verify image size is reasonable**

```bash
docker images picklebot:test
```

Expected: Image size around 300-500MB

---

### Task 5: Update README with Docker instructions

**Files:**
- Modify: `README.md`

**Step 1: Add Docker section to README**

Add after the Commands section:

```markdown
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
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add Docker instructions to README"
```
