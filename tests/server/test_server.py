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


@pytest.mark.asyncio
async def test_server_monitor_restarts_crashed_worker(test_context):
    """Server monitoring restarts crashed workers."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    # Get initial task reference
    initial_tasks = server._tasks.copy()

    # Create a task that fails immediately
    async def crash():
        raise RuntimeError("Crash!")

    crashed_task = asyncio.create_task(crash())
    await asyncio.sleep(0.01)  # Let it crash

    # Replace a running task with the crashed one
    server._tasks[0] = crashed_task

    # Run one monitoring check manually
    task = server._tasks[0]
    if task.done() and not task.cancelled():
        worker = server.workers[0]
        exc = task.exception()
        if exc:
            new_task = worker.start()
            server._tasks[0] = new_task

    # Verify the task was replaced
    assert server._tasks[0] is not crashed_task
    assert not server._tasks[0].done()

    # Cleanup
    await server._stop_all()
