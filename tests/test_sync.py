import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from asgiref.sync import async_to_sync, sync_to_async


@pytest.mark.asyncio
async def test_sync_to_async():
    """
    Tests we can call sync functions from an async thread
    (even if the number of thread workers is less than the number of calls)
    """
    # Define sync function
    def sync_function():
        time.sleep(1)
        return 42

    # Wrap it
    async_function = sync_to_async(sync_function)
    # Check it works right
    start = time.monotonic()
    result = await async_function()
    end = time.monotonic()
    assert result == 42
    assert end - start >= 1
    # Set workers to 1, call it twice and make sure that works right
    loop = asyncio.get_event_loop()
    old_executor = loop._default_executor
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
    try:
        start = time.monotonic()
        await asyncio.wait([async_function(), async_function()])
        end = time.monotonic()
        # It should take at least 2 seconds as there's only one worker.
        assert end - start >= 2
    finally:
        loop.set_default_executor(old_executor)


@pytest.mark.asyncio
async def test_sync_to_async_decorator():
    """
    Tests sync_to_async as a decorator
    """
    # Define sync function
    @sync_to_async
    def test_function():
        time.sleep(1)
        return 43

    # Check it works right
    result = await test_function()
    assert result == 43


@pytest.mark.asyncio
async def test_sync_to_async_method_decorator():
    """
    Tests sync_to_async as a method decorator
    """
    # Define sync function
    class TestClass:
        @sync_to_async
        def test_method(self):
            time.sleep(1)
            return 44

    # Check it works right
    instance = TestClass()
    result = await instance.test_method()
    assert result == 44


@pytest.mark.asyncio
async def test_async_to_sync_to_async():
    """
    Tests we can call async functions from a sync thread created by async_to_sync
    (even if the number of thread workers is less than the number of calls)
    """
    result = {}

    # Define async function
    async def inner_async_function():
        result["worked"] = True
        return 65

    # Define sync function
    def sync_function():
        return async_to_sync(inner_async_function)()

    # Wrap it
    async_function = sync_to_async(sync_function)
    # Check it works right
    number = await async_function()
    assert number == 65
    assert result["worked"]


def test_async_to_sync():
    """
    Tests we can call async_to_sync outside of an outer event loop.
    """
    result = {}

    # Define async function
    async def inner_async_function():
        await asyncio.sleep(0)
        result["worked"] = True
        return 84

    # Run it
    sync_function = async_to_sync(inner_async_function)
    number = sync_function()
    assert number == 84
    assert result["worked"]


def test_async_to_sync_decorator():
    """
    Tests we can call async_to_sync as a function decorator
    """
    result = {}

    # Define async function
    @async_to_sync
    async def test_function():
        await asyncio.sleep(0)
        result["worked"] = True
        return 85

    # Run it
    number = test_function()
    assert number == 85
    assert result["worked"]


def test_async_to_sync_method_decorator():
    """
    Tests we can call async_to_sync as a function decorator
    """
    result = {}

    # Define async function
    class TestClass:
        @async_to_sync
        async def test_function(self):
            await asyncio.sleep(0)
            result["worked"] = True
            return 86

    # Run it
    instance = TestClass()
    number = instance.test_function()
    assert number == 86
    assert result["worked"]


@pytest.mark.asyncio
async def test_async_to_sync_in_async():
    """
    Makes sure async_to_sync bails if you try to call it from an async loop
    """

    # Define async function
    async def inner_async_function():
        return 84

    # Run it
    sync_function = async_to_sync(inner_async_function)
    with pytest.raises(RuntimeError):
        sync_function()


def test_async_to_sync_in_thread():
    """
    Tests we can call async_to_sync inside a thread
    """
    result = {}

    # Define async function
    @async_to_sync
    async def test_function():
        await asyncio.sleep(0)
        result["worked"] = True

    # Make a thread
    thread = threading.Thread(target=test_function)
    thread.start()
    thread.join()

    # Run it
    assert result["worked"]
