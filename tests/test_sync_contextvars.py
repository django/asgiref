import asyncio
import time

import pytest

from asgiref.sync import async_to_sync, sync_to_async

contextvars = pytest.importorskip("contextvars")

foo = contextvars.ContextVar("foo")


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
