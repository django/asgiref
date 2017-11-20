import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor, Future


def callable_application(func):
    """
    Function/method decorator that turns an async callable that takes
    (conntype, receive, send) into an ASGI application by doing the
    double-callable step internally.
    """
    def outer(conntype):
        async def inner(receive, send):
            await func(conntype, receive, send)
        return inner
    return outer
