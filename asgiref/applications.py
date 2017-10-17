import asyncio
import functools
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, Future


# TODO: Add number of threads option?
def sync_application(cls):
    """
    Class decorator/wrapper that wraps a sync ASGI application into an async ASGI application.

    Each call to the __call__ method will be done in a separate thread, and
    replies will be bounced out to the main thread before being sent to the
    ASGI server.

    One thread pool will be made per application.
    """
    # Make the thread pool
    pool = ThreadPoolExecutor()
    # Make a new specalist subclass of ThreadedApplication
    threaded_subclass = type(
        "ConcreteThreadedApplication",
        (ThreadedApplication, ),
        {
            "application": cls,
            "pool": pool,
        },
    )
    return threaded_subclass


class CallBouncer:
    """
    Utility class which turns an awaitable that only works on the main thread
    into a synchronous callable that works in a subthread.

    Must be initialised from the main thread.
    """

    def __init__(self, awaitable):
        assert threading.current_thread() == threading.main_thread()
        self.awaitable = awaitable
        self.main_event_loop = asyncio.get_event_loop()

    def __call__(self, *args, **kwargs):
        # Make a future for the return information
        call_result = Future()
        # Use call_soon_threadsafe to schedule a synchronous callback on the
        # main event loop's thread
        self.main_event_loop.call_soon_threadsafe(
            asyncio.ensure_future,
            self.main_wrap(
                {
                    "args": args,
                    "kwargs": kwargs,
                },
                call_result,
            ),
        )
        # Wait for results from the future.
        call_result.result()

    async def main_wrap(self, args, call_result):
        """
        Wraps the awaitable with something that puts the result into the
        result/exception future.
        """
        try:
            result = await self.awaitable(*args["args"], **args["kwargs"])
        except Exception as e:
            call_result.set_exception(e)
        else:
            call_result.set_result(result)


class ThreadedApplication:
    """
    Wraps a synchronous-style application (a callable that returns a callable)
    so that it presents as an asynchronous application.

    Needs to be subclassed to provide the "application" and "pool" class body
    attributes before it's run - this can either be done using the
    sync_application decorator, or manually.
    """

    threadpool = ThreadPoolExecutor()

    def __init__(self, conntype):
        # We get the main event loop here as if we try to fetch from inside
        # a thread we will get a thread-specific one.
        self.instance = self.application(conntype)

    async def __call__(self, receive, send):
        """
        Main entrypoint that runs the application in a thread.
        """
        # Wrap the async send function
        self.thread_send = CallBouncer(send)
        while True:
            # Get the next event
            message = await receive()
            # Run it in the pool
            self.threadpool.submit(self.thread_handler, message)

    def thread_handler(self, message):
        """
        Wraps the sync application with exception handling.
        """
        try:
            self.instance(message, self.thread_send)
        except Exception as e:
            traceback.print_exc()
            raise e
