import asyncio
import contextvars
import sys
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


@pytest.mark.asyncio
async def test_sync_to_async_contextvars_with_custom_context():
    """
    Test that passing a custom context to `sync_to_async` ensures that changes to
    context variables within the synchronous function are isolated to the
    provided context and do not affect the caller's context. Specifically,
    verifies that modifications to a context variable inside the
    sync function are reflected only in the custom context and not in the
    outer context.
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
    context = contextvars.copy_context()
    async_function = sync_to_async(sync_function, context=context)
    assert await async_function() == 42

    # verify that the current context remains unchanged
    assert foo.get() == "bar"

    # verify that the custom context reflects the changes made within the
    # sync function
    assert context.get(foo) == "baz"


@pytest.mark.asyncio
@pytest.mark.skipif(sys.version_info < (3, 11), reason="requires python3.11")
async def test_sync_to_async_contextvars_with_custom_context_and_parallel_tasks():
    """
    Test that using a custom context with `sync_to_async` and asyncio tasks
    isolates contextvars changes, leaving the original context unchanged and
    reflecting all modifications in the custom context.
    """
    # Ensure outermost detection works
    # Wrap it
    foo.set("")

    def sync_function():
        foo.set(foo.get() + "1")
        return 1

    async def async_function():
        foo.set(foo.get() + "1")
        return 1

    context = contextvars.copy_context()

    await asyncio.gather(
        sync_to_async(sync_function, context=context)(),
        sync_to_async(sync_function, context=context)(),
        asyncio.create_task(async_function(), context=context),
        asyncio.create_task(async_function(), context=context),
    )

    # verify that the current context remains unchanged
    assert foo.get() == ""

    # verify that the custom context reflects the changes made within the
    # sync function
    assert context.get(foo) == "1111"


def test_async_to_sync_contextvars():
    """
    Tests to make sure that contextvars from the calling context are
    present in the called context, and that any changes in the called context
    are then propagated back to the calling context.
    """
    # Define async function
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
