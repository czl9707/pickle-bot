FROM python:3.13-slim

WORKDIR /app
EXPOSE 8000

RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

RUN mkdir -p ~/.pickle-bot

CMD ["uv", "run", "picklebot", "server"]
