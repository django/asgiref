import sys
from functools import wraps


def sync_generator_to_async(sync_generator_fn, impl, thread_sensitive=False):
    if sys.version_info <= (3, 5):
        raise RuntimeError("async generators aren't supported on python <= 3.5")

    # the generator func might do blocking operations before it "yields",
    # so convert the function itself (not the generator!) to async first
    async_fn = impl(sync_generator_fn, thread_sensitive)

    @wraps(sync_generator_fn)
    async def wrapper(*args, **kwargs):
        # the async function returns a sync generator
        sync_generator = await async_fn(*args, **kwargs)

        # since a generator is technically an iterable,
        # we can defer this conversion to sync_iterable_to_async
        async_generator = sync_iterable_to_async(sync_generator, impl, thread_sensitive)

        async for item in async_generator:
            yield item

    return wrapper


async def sync_iterable_to_async(sync_iterable, impl, thread_sensitive=False):
    # asyncio expects `StopAsyncIteration` in place of `StopIteration`,
    # so here's a modified in-built `next` function to handle this
    def next_sync(it):
        try:
            return next(it)
        except StopIteration:
            raise StopAsyncIteration

    next_async = impl(next_sync, thread_sensitive)

    # async version of the in-built `iter` function
    iter_async = impl(iter, thread_sensitive)
    # iter_async() doesn't actually return an async iterable!
    sync_iterator = await iter_async(sync_iterable)

    while True:
        try:
            yield await next_async(sync_iterator)
        except StopAsyncIteration:
            return
