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

    def __call__(self, *args, **kwargs):
        # Make a future for the return information
        call_result = Future()
        threadlocal = False
        try:
            main_event_loop = asyncio.get_event_loop()
        except RuntimeError:
            # There's no event loop in this thread. Look for the threadlocal if
            # we're inside SyncToAsync
            main_event_loop = getattr(SyncToAsync.threadlocal, "main_event_loop", None)
            threadlocal = True
        if main_event_loop and main_event_loop.is_running():
            if threadlocal:
                # Schedule a synchronous callback to the thread local event loop.
                main_event_loop.call_soon_threadsafe(
                    main_event_loop.create_task,
                    self.main_wrap(args, kwargs, call_result)
                )
            else:
                # Calling coroutine from main async thread will cause race.
                # Call the coroutine in a new thread.
                def run_in_thread():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(self.main_wrap(args, kwargs, call_result))
                    finally:
                        loop.close()
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
        else:
            # Make our own event loop and run inside that.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.main_wrap(args, kwargs, call_result))
            finally:
                try:
                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    loop.close()
                    asyncio.set_event_loop(main_event_loop)
        # Wait for results from the future.
        return call_result.result()

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        return functools.partial(self.__call__, parent)

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

    # If they've set ASGI_THREADS, update the default asyncio executor for now
    if "ASGI_THREADS" in os.environ:
        loop = asyncio.get_event_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=int(os.environ["ASGI_THREADS"])))

    threadlocal = threading.local()

    def __init__(self, func):
        self.func = func

    async def __call__(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(
            None,
            functools.partial(self.thread_handler, loop, *args, **kwargs),
        )
        return await asyncio.wait_for(future, timeout=None)

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        return functools.partial(self.__call__, parent)

    def thread_handler(self, loop, *args, **kwargs):
        """
        Wraps the sync application with exception handling.
        """
        # Set the threadlocal for AsyncToSync
        self.threadlocal.main_event_loop = loop
        # Run the function
        return self.func(*args, **kwargs)


# Lowercase is more sensible for most things
sync_to_async = SyncToAsync
async_to_sync = AsyncToSync
