import typing
from functools import wraps


def sync_generator_fn_to_async(sync_generator_fn, impl, thread_sensitive=False):
    # the generator func might do blocking operations before it "yields",
    # so convert the function itself (not the generator!) to async first
    async_generator_fn = impl(sync_generator_fn, thread_sensitive)

    @wraps(sync_generator_fn)
    def wrapper(*args, **kwargs):

        async def get_sync_iterable():
            # the async generator function should return a sync generator.
            # since a generator is also an iterable, it is compatible with SyncToAsyncIterable
            return await async_generator_fn(*args, **kwargs)

        return SyncToAsyncIterable(get_sync_iterable, impl, thread_sensitive)

    return wrapper


def sync_iterable_to_async(sync_iterable, impl, thread_sensitive=False):

    async def get_sync_iterable():
        return sync_iterable

    return SyncToAsyncIterable(get_sync_iterable, impl, thread_sensitive)


class SyncToAsyncIterable():
    def __init__(
        self,
        get_sync_iterable: typing.Callable[[], typing.Awaitable[typing.Iterable]],
        impl: typing.Callable,
        thread_sensitive: bool,
    ):
        """An an async version of iterable returned by ``get_sync_iterable``"""

        self.get_sync_iterable = get_sync_iterable

        # async versions of the `next` and `iter` functions
        self.next_async = impl(_next_, thread_sensitive)
        self.iter_async = impl(iter, thread_sensitive)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not hasattr(self, 'sync_iterator'):
            # one-time setup of the internal iterator
            sync_iterable = await self.get_sync_iterable()
            self.sync_iterator = await self.iter_async(sync_iterable)

        return await self.next_async(self.sync_iterator)


def _next_(it):
    """
    asyncio expects `StopAsyncIteration` in place of `StopIteration`,
    so here's a modified in-built `next` function that can handle this.
    """
    try:
        return next(it)
    except StopIteration:
        raise StopAsyncIteration
