"""Tests for SharedContext."""

import asyncio

import pytest


@pytest.mark.anyio
async def test_agent_queue_is_lazy(test_context):
    """agent_queue should be created lazily on first access."""
    # Before access, internal storage should be None
    assert test_context._agent_queue is None

    # After access, should be a Queue
    queue = test_context.agent_queue
    assert isinstance(queue, asyncio.Queue)

    # Same queue on subsequent access
    assert test_context.agent_queue is queue
