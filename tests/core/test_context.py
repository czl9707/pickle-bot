"""Tests for SharedContext."""

import asyncio

import pytest


@pytest.mark.anyio
async def test_register_and_get_future(test_context):
    """register_future and get_future should work correctly."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    test_context.register_future("test-job-id", future)

    # Should retrieve and remove the future
    retrieved = test_context.get_future("test-job-id")
    assert retrieved is future

    # Should return None on second access
    retrieved_again = test_context.get_future("test-job-id")
    assert retrieved_again is None


@pytest.mark.anyio
async def test_get_future_returns_none_for_unknown(test_context):
    """get_future should return None for unknown job_id."""
    result = test_context.get_future("unknown-job-id")
    assert result is None
