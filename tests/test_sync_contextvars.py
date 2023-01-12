import asyncio
import contextvars
import threading
import time

import pytest

from asgiref.sync import ThreadSensitiveContext, async_to_sync, sync_to_async

foo: "contextvars.ContextVar[str]" = contextvars.ContextVar("foo")


@pytest.mark.asyncio
async def test_thread_sensitive_with_context_different():
    result_1 = {}
    result_2 = {}

    @sync_to_async
    def store_thread(result):
        result["thread"] = threading.current_thread()

    async def fn(result):
        async with ThreadSensitiveContext():
            await store_thread(result)

    # Run it (in true parallel!)
    await asyncio.wait(
        [asyncio.create_task(fn(result_1)), asyncio.create_task(fn(result_2))]
    )

    # They should not have run in the main thread, and on different threads
    assert result_1["thread"] != threading.current_thread()
    assert result_1["thread"] != result_2["thread"]


@pytest.mark.asyncio
async def test_sync_to_async_contextvars():
    """
    Tests to make sure that contextvars from the calling context are
    present in the called context, and that any changes in the called context
    are then propagated back to the calling context.
    """
    # Define sync function
    def sync_function():
        time.sleep(1)
        assert foo.get() == "bar"
        foo.set("baz")
        return 42

    # Ensure outermost detection works
    # Wrap it
    foo.set("bar")
    async_function = sync_to_async(sync_function)
    assert await async_function() == 42
    assert foo.get() == "baz"


def test_async_to_sync_contextvars():
    """
    Tests to make sure that contextvars from the calling context are
    present in the called context, and that any changes in the called context
    are then propagated back to the calling context.
    """
    # Define sync function
    async def async_function():
        await asyncio.sleep(1)
        assert foo.get() == "bar"
        foo.set("baz")
        return 42

    # Ensure outermost detection works
    # Wrap it
    foo.set("bar")
    sync_function = async_to_sync(async_function)
    assert sync_function() == 42
    assert foo.get() == "baz"
