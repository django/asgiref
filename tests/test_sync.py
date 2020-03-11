import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from unittest import TestCase

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

    # Ensure outermost detection works
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
async def test_nested_sync_to_async_retains_wrapped_function_attributes():
    """
    Tests that attributes of functions wrapped by sync_to_async are retained
    """

    def enclosing_decorator(attr_value):
        @wraps(attr_value)
        def wrapper(f):
            f.attr_name = attr_value
            return f

        return wrapper

    @enclosing_decorator("test_name_attribute")
    @sync_to_async
    def test_function():
        pass

    assert test_function.attr_name == "test_name_attribute"
    assert test_function.__name__ == "test_function"


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
async def test_sync_to_async_method_self_attribute():
    """
    Tests sync_to_async on a method copies __self__
    """

    # Define sync function
    class TestClass:
        def test_method(self):
            time.sleep(0.1)
            return 45

    # Check it works right
    instance = TestClass()
    method = sync_to_async(instance.test_method)
    result = await method()
    assert result == 45

    # Check __self__ has been copied
    assert method.__self__ == instance


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
        result["thread"] = threading.current_thread()
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
    # Make sure that it didn't needlessly make a new async loop
    assert result["thread"] == threading.current_thread()


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

    # Make a thread and run it
    thread = threading.Thread(target=test_function)
    thread.start()
    thread.join()
    assert result["worked"]


def test_async_to_async_method_self_attribute():
    """
    Tests async_to_async on a method copies __self__.
    """
    # Define async function.
    class TestClass:
        async def test_function(self):
            await asyncio.sleep(0)
            return 45

    # Check it works right.
    instance = TestClass()
    sync_function = async_to_sync(instance.test_function)
    number = sync_function()
    assert number == 45

    # Check __self__ has been copied.
    assert sync_function.__self__ is instance


def test_thread_sensitive_outside_sync():
    """
    Tests that thread_sensitive SyncToAsync where the outside is sync code runs
    in the main thread.
    """

    result = {}

    # Middle async function
    @async_to_sync
    async def middle():
        await inner()

    # Inner sync function
    def inner():
        result["thread"] = threading.current_thread()

    inner = sync_to_async(inner, thread_sensitive=True)

    # Run it
    middle()
    assert result["thread"] == threading.current_thread()


@pytest.mark.asyncio
async def test_thread_sensitive_outside_async():
    """
    Tests that thread_sensitive SyncToAsync where the outside is async code runs
    in a single, separate thread.
    """

    result_1 = {}
    result_2 = {}

    # Outer sync function
    def outer(result):
        middle(result)

    outer = sync_to_async(outer, thread_sensitive=True)

    # Middle async function
    @async_to_sync
    async def middle(result):
        await inner(result)

    # Inner sync function
    def inner(result):
        result["thread"] = threading.current_thread()

    inner = sync_to_async(inner, thread_sensitive=True)

    # Run it (in supposed parallel!)
    await asyncio.wait([outer(result_1), inner(result_2)])

    # They should not have run in the main thread, but in the same thread
    assert result_1["thread"] != threading.current_thread()
    assert result_1["thread"] == result_2["thread"]


def test_thread_sensitive_double_nested_sync():
    """
    Tests that thread_sensitive SyncToAsync nests inside itself where the
    outside is sync.
    """

    result = {}

    # Async level 1
    @async_to_sync
    async def level1():
        await level2()

    # Sync level 2
    def level2():
        level3()

    level2 = sync_to_async(level2, thread_sensitive=True)

    # Async level 3
    @async_to_sync
    async def level3():
        await level4()

    # Sync level 2
    def level4():
        result["thread"] = threading.current_thread()

    level4 = sync_to_async(level4, thread_sensitive=True)

    # Run it
    level1()
    assert result["thread"] == threading.current_thread()


@pytest.mark.asyncio
async def test_thread_sensitive_double_nested_async():
    """
    Tests that thread_sensitive SyncToAsync nests inside itself where the
    outside is async.
    """

    result = {}

    # Sync level 1
    def level1():
        level2()

    level1 = sync_to_async(level1, thread_sensitive=True)

    # Async level 2
    @async_to_sync
    async def level2():
        await level3()

    # Sync level 3
    def level3():
        level4()

    level3 = sync_to_async(level3, thread_sensitive=True)

    # Async level 4
    @async_to_sync
    async def level4():
        result["thread"] = threading.current_thread()

    # Run it
    await level1()
    assert result["thread"] == threading.current_thread()


class ASGITest(TestCase):
    """
    Tests collection of async cases inside classes
    """

    @async_to_sync
    async def test_wrapped_case_is_collected(self):
        self.assertTrue(True)


def test_sync_to_async_detected_as_coroutinefunction():
    """
    Tests that SyncToAsync functions are detected as coroutines.
    """

    def sync_func():
        return

    assert not asyncio.iscoroutinefunction(sync_to_async)
    assert asyncio.iscoroutinefunction(sync_to_async(sync_func))
