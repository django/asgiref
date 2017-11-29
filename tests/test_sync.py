import asyncio
import pytest
import time

from asgiref.sync import SyncToAsync
from concurrent.futures import ThreadPoolExecutor


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
