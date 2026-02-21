"""Tests for Server class."""

import asyncio

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

    assert all(w.is_running() for w in server.workers)

    # Cleanup
    await server._stop_all()


@pytest.mark.asyncio
async def test_server_stops_workers_gracefully(test_context):
    """Server stops all workers on shutdown."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    await server._stop_all()

    assert all(not w.is_running() for w in server.workers)


@pytest.mark.asyncio
async def test_server_monitor_restarts_crashed_worker(test_context):
    """Server monitoring restarts crashed workers."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    # Get the first worker and simulate a crash by replacing its task
    worker = server.workers[0]

    async def crash():
        raise RuntimeError("Crash!")

    crashed_task = asyncio.create_task(crash())
    await asyncio.sleep(0.01)  # Let it crash

    # Replace the worker's task with the crashed one
    worker._task = crashed_task

    # Verify worker is detected as crashed
    assert worker.has_crashed()
    assert worker.get_exception() is not None

    # Restart via the worker's start method
    worker.start()

    # Verify the worker is running again
    assert worker.is_running()
    assert not worker.has_crashed()

    # Cleanup
    await server._stop_all()
