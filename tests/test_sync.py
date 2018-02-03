import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from asgiref.sync import AsyncToSync, SyncToAsync


@pytest.mark.asyncio
async def test_sync_to_async():
    """
    Tests we can call sync functions from an async thread
    (even if the number of thread workers is less than the number of calls)
    """
    # Define sync function
    def sync_function():
        time.sleep(1)
    # Wrap it
    async_function = SyncToAsync(sync_function)
    # Check it works right
    start = time.monotonic()
    await async_function()
    end = time.monotonic()
    assert end - start >= 1
    # Set workers to 1, call it twice and make sure that works right
    old_threadpool, SyncToAsync.threadpool = SyncToAsync.threadpool, ThreadPoolExecutor(max_workers=1)
    try:
        start = time.monotonic()
        await asyncio.wait([async_function(), async_function()])
        end = time.monotonic()
        # It should take at least 2 seconds as there's only one worker.
        assert end - start >= 2
    finally:
        SyncToAsync.threadpool = old_threadpool


@pytest.mark.asyncio
async def test_async_to_sync_to_async():
    """
    Tests we can call async functions from a sync thread created by AsyncToSync
    (even if the number of thread workers is less than the number of calls)
    """
    result = {}

    # Define async function
    async def inner_async_function():
        result["worked"] = True

    # Define sync function
    def sync_function():
        AsyncToSync(inner_async_function)()

    # Wrap it
    async_function = SyncToAsync(sync_function)
    # Check it works right
    await async_function()
    assert result["worked"]
