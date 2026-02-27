"""Tests for Server class."""

import asyncio

import pytest

from picklebot.server.server import Server


@pytest.mark.anyio
async def test_server_starts_workers(test_context):
    """Server starts all workers as tasks."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    assert all(w.is_running() for w in server.workers)

    # Cleanup
    await server._stop_all()


@pytest.mark.anyio
async def test_server_stops_workers_gracefully(test_context):
    """Server stops all workers on shutdown."""
    server = Server(test_context)
    server._setup_workers()
    server._start_workers()

    await server._stop_all()

    assert all(not w.is_running() for w in server.workers)


@pytest.mark.anyio
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


def test_server_uses_context_queue():
    """Server should not create its own queue, use context's."""
    from unittest.mock import MagicMock, patch

    context = MagicMock()
    context.agent_queue = asyncio.Queue()
    context.config.messagebus.enabled = False
    context.config.api = None

    with (
        patch("picklebot.server.server.AgentDispatcherWorker"),
        patch("picklebot.server.server.CronWorker"),
    ):
        server = Server(context)

        # Server should not have its own agent_queue
        assert not hasattr(server, "agent_queue")


@pytest.mark.anyio
async def test_server_starts_config_reloader(test_context):
    """Server should start ConfigReloader alongside workers."""
    from unittest.mock import patch

    with patch("picklebot.server.server.ConfigReloader") as mock_reloader:
        mock_instance = mock_reloader.return_value
        server = Server(test_context)

        # Run setup (not full run, just setup)
        server._setup_workers()

        # ConfigReloader should be created and started
        mock_reloader.assert_called_once_with(test_context.config)
        mock_instance.start.assert_called_once()

        # Cleanup
        await server._stop_all()
