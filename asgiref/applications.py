import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


# TODO: Add number of threads option?
def threaded_class_application(cls):
    """
    Class decorator that wraps a sync class into an ASGI application coroutine.

    The class will be passed type and reply into its constructor, and next
    will be awaited on and messages fed into the class' __call__ method.

    Each call to the __call__ method will be done in a separate thread, and
    replies will be bounced out to the main thread before being sent to the
    ASGI server.

    One thread pool will be made per application.
    """
    # Make the thread pool
    pool = ThreadPoolExecutor()
    # Make a coroutine to pass back out
    async def inner(type, next, reply):
        # Make a reply that switches to the main thread, then disp
        def main_reply(message):
            print("back in main reply")
            asyncio.ensure_future(reply, message)
        def thread_reply(message):
            print("thread reply")
            asyncio.get_event_loop().call_soon_threadsafe(main_reply, message)
        instance = cls(type, thread_reply)
        while True:
            # Get the next event
            message = await next()
            # Run it in the pool
            print("Submitting to thread")
            pool.submit(instance, message)
    return inner
