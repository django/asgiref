import asyncio
import functools
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor

try:
    import contextvars  # Python 3.7+ only.
except ImportError:
    contextvars = None


class AsyncToSync:
    """
    Utility class which turns an awaitable that only works on the thread with
    the event loop into a synchronous callable that works in a subthread.

    Must be initialised from the main thread.
    """

    # Maps launched Tasks to the threads that launched them
    launch_map = {}

    def __init__(self, awaitable, force_new_loop=False):
        self.awaitable = awaitable
        if force_new_loop:
            # They have asked that we always run in a new sub-loop.
            self.main_event_loop = None
        else:
            try:
                self.main_event_loop = asyncio.get_event_loop()
            except RuntimeError:
                # There's no event loop in this thread. Look for the threadlocal if
                # we're inside SyncToAsync
                self.main_event_loop = getattr(
                    SyncToAsync.threadlocal, "main_event_loop", None
                )

    def __call__(self, *args, **kwargs):
        # You can't call AsyncToSync from a thread with a running event loop
        try:
            event_loop = asyncio.get_event_loop()
        except RuntimeError:
            pass
        else:
            if event_loop.is_running():
                raise RuntimeError(
                    "You cannot use AsyncToSync in the same thread as an async event loop - "
                    "just await the async function directly."
                )
        # Make a future for the return information
        call_result = Future()
        # Get the source thread
        source_thread = threading.current_thread()
        # Use call_soon_threadsafe to schedule a synchronous callback on the
        # main event loop's thread if it's there, otherwise make a new loop
        # in this thread.
        if not (self.main_event_loop and self.main_event_loop.is_running()):
            # Make our own event loop and run inside that.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.main_wrap(args, kwargs, call_result, source_thread)
                )
            finally:
                try:
                    if hasattr(loop, "shutdown_asyncgens"):
                        loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    loop.close()
                    asyncio.set_event_loop(self.main_event_loop)
        else:
            self.main_event_loop.call_soon_threadsafe(
                self.main_event_loop.create_task,
                self.main_wrap(args, kwargs, call_result, source_thread),
            )
        # Wait for results from the future.
        return call_result.result()

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        func = functools.partial(self.__call__, parent)
        return functools.update_wrapper(func, self.awaitable)

    async def main_wrap(self, args, kwargs, call_result, source_thread):
        """
        Wraps the awaitable with something that puts the result into the
        result/exception future.
        """
        current_task = SyncToAsync.get_current_task()
        self.launch_map[current_task] = source_thread
        try:
            result = await self.awaitable(*args, **kwargs)
        except Exception as e:
            call_result.set_exception(e)
        else:
            call_result.set_result(result)
        finally:
            del self.launch_map[current_task]


class SyncToAsync:
    """
    Utility class which turns a synchronous callable into an awaitable that
    runs in a threadpool. It also sets a threadlocal inside the thread so
    calls to AsyncToSync can escape it.

    If thread_sensitive is passed, the code will run in the same thread as any
    outer code. This is needed for underlying Python code that is not
    threadsafe (for example, code which handles SQLite database connections).

    If the outermost program is async (i.e. SyncToAsync is outermost), then
    this will be a dedicated single sub-thread that all sync code runs in,
    one after the other. If the outermost program is sync (i.e. AsyncToSync is
    outermost), this will just be the main thread and will block the async loop,
    as it's likely the sync code wants to be on the main thread anyway.

    Determining "outermostness" is done by looking at the launch_map pairs
    for the current thread/task.
    """

    # If they've set ASGI_THREADS, update the default asyncio executor for now
    if "ASGI_THREADS" in os.environ:
        loop = asyncio.get_event_loop()
        loop.set_default_executor(
            ThreadPoolExecutor(max_workers=int(os.environ["ASGI_THREADS"]))
        )

    # Maps launched threads to the coroutines that spawned them
    launch_map = {}

    # Storage for main event loop references
    threadlocal = threading.local()

    # Single-thread executor for thread-sensitive code
    single_thread_executor = ThreadPoolExecutor(max_workers=1)

    def __init__(self, func, thread_sensitive=False):
        self.func = func
        self._thread_sensitive = thread_sensitive

    async def __call__(self, *args, **kwargs):
        loop = asyncio.get_event_loop()

        # Work out what thread to run the code in
        if self._thread_sensitive:
            if self._is_outermost_sync():
                # Program has outermost layer as sync, so run the code blocking.
                return self.func(*args, **kwargs)
            else:
                # Program has outermost layer as async, so use the single-thread pool.
                executor = self.single_thread_executor
        else:
            executor = None  # Use default

        if contextvars is not None:
            context = contextvars.copy_context()
            child = functools.partial(self.func, *args, **kwargs)
            func = context.run
            args = (child,)
            kwargs = {}
        else:
            func = self.func

        # Run the code in the right thread
        future = loop.run_in_executor(
            executor,
            functools.partial(
                self.thread_handler,
                loop,
                self.get_current_task(),
                func,
                *args,
                **kwargs
            ),
        )
        return await asyncio.wait_for(future, timeout=None)

    def __get__(self, parent, objtype):
        """
        Include self for methods
        """
        return functools.partial(self.__call__, parent)

    def thread_handler(self, loop, source_task, func, *args, **kwargs):
        """
        Wraps the sync application with exception handling.
        """
        # Set the threadlocal for AsyncToSync
        self.threadlocal.main_event_loop = loop
        # Set the task mapping (used for the locals module)
        current_thread = threading.current_thread()
        self.launch_map[current_thread] = source_task
        # Run the function
        try:
            return func(*args, **kwargs)
        finally:
            del self.launch_map[current_thread]

    @staticmethod
    def get_current_task():
        """
        Cross-version implementation of asyncio.current_task()

        Returns None if there is no task.
        """
        try:
            if hasattr(asyncio, "current_task"):
                # Python 3.7 and up
                return asyncio.current_task()
            else:
                # Python 3.6
                return asyncio.Task.current_task()
        except RuntimeError:
            return None

    @classmethod
    def _is_outermost_sync(cls):
        """
        Determines if the outermost call is AsyncToSync
        """
        # Get starting conditions
        current_task = cls.get_current_task()
        current_thread = threading.current_thread()
        frame_is_sync = current_task is None
        # Step up through each task/thread to its parent, stopping when we run out of parents
        # Where we stop determines what the outermost type of call is
        for i in range(1000):
            if frame_is_sync:
                current_task = SyncToAsync.launch_map.get(current_thread, None)
                frame_is_sync = False
                if current_task is None:
                    return True
            else:
                current_thread = AsyncToSync.launch_map.get(current_task, None)
                frame_is_sync = True
                if current_thread is None:
                    return False
        raise Exception("Infinite loop determining outermost sync type")


# Lowercase is more sensible for most things
sync_to_async = SyncToAsync
async_to_sync = AsyncToSync
