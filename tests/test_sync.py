import pytest
import time

from asgiref.sync import SyncToAsync


@pytest.mark.asyncio
async def test_sync_to_async():
    """
    Tests we can call sync functions from an async thread.
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
