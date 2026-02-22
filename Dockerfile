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
