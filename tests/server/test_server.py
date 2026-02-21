"""Tests for Server class."""

import pytest

from picklebot.server.server import Server


@pytest.mark.asyncio
async def test_server_creates_workers(test_context):
    """Server creates AgentWorker and CronWorker."""
    server = Server(test_context)

    server._setup_workers()

    assert len(server.workers) == 2  # Agent + Cron


@pytest.mark.asyncio
async def test_server_starts_workers(test_context):
    """Server starts all workers as tasks."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    assert len(server._tasks) == 2
    assert all(not t.done() for t in server._tasks)

    # Cleanup
    await server._stop_all()


@pytest.mark.asyncio
async def test_server_stops_workers_gracefully(test_context):
    """Server stops all workers on shutdown."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    await server._stop_all()

    assert all(t.done() for t in server._tasks)
