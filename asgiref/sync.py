import asyncio
import functools
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor


class AsyncToSync:
    """
    Utility class which turns an awaitable that only works on the thread with
    the event loop into a synchronous callable that works in a subthread.

    Must be initialised from the main thread.
    """

    def __init__(self, awaitable):
        self.awaitable = awaitable
        try:
            self.main_event_loop = asyncio.get_event_loop()
        except RuntimeError:
            # There's no event loop in this thread. Look for the threadlocal if
            # we're inside SyncToAsync
            self.main_event_loop = getattr(SyncToAsync.threadlocal, "main_event_loop", None)
            if self.main_event_loop is None:
                raise RuntimeError(
                    "You cannot instantiate AsyncToSync inside a thread that wasn't made using SyncToAsync"
                )

    def __call__(self, *args, **kwargs):
        # Make a future for the return information
        call_result = Future()
        # Use call_soon_threadsafe to schedule a synchronous callback on the
        # main event loop's thread
        if not self.main_event_loop.is_running():
            raise RuntimeError("Cannot call async functions without an event loop running")
        self.main_event_loop.call_soon_threadsafe(
            asyncio.ensure_future,
            self.main_wrap(
                args,
                kwargs,
                call_result,
            ),
        )
        # Wait for results from the future.
        call_result.result()

    async def main_wrap(self, args, kwargs, call_result):
        """
        Wraps the awaitable with something that puts the result into the
        result/exception future.
        """
        try:
            result = await self.awaitable(*args, **kwargs)
        except Exception as e:
            call_result.set_exception(e)
        else:
            call_result.set_result(result)


class SyncToAsync:
    """
    Utility class which turns a synchronous callable into an awaitable that
    runs in a threadpool. It also sets a threadlocal inside the thread so
    calls to AsyncToSync can escape it.
    """

    threadpool = ThreadPoolExecutor(max_workers=os.environ.get("ASGI_THREADS", None))
    threadlocal = threading.local()

    def __init__(self, func):
        self.func = func

    async def __call__(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            self.threadpool,
            functools.partial(self.thread_handler, loop, *args, **kwargs),
        )
        return await asyncio.wait_for(future, timeout=None)

    def thread_handler(self, loop, *args, **kwargs):
        """
        Wraps the sync application with exception handling.
        """
        # Set the threadlocal for AsyncToSync
        self.threadlocal.main_event_loop = loop
        # Run the function
        try:
            self.func(*args, **kwargs)
        except Exception as e:
            raise e


# Decorator versions that will work on methods too.
def sync_to_async(func):
    async_func = SyncToAsync(func)

    async def inner(*args, **kwargs):
        return await async_func(*args, **kwargs)

    return inner


def async_to_sync(func):
    sync_func = AsyncToSync(func)

    def inner(*args, **kwargs):
        return sync_func(*args, **kwargs)

    return inner
