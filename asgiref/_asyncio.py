__all__ = [
    "get_running_loop",
    "create_task_threadsafe",
    "wrap_task_context",
    "run_in_executor",
]

import asyncio
import concurrent.futures
import contextvars
import functools
import sys
import types
from asyncio import get_running_loop
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Generic, Protocol, TypeVar, Union

from ._context import restore_context as _restore_context

_R = TypeVar("_R")

Coro = Coroutine[Any, Any, _R]


def create_task_threadsafe(
    loop: asyncio.AbstractEventLoop, awaitable: Coro[object]
) -> None:
    loop.call_soon_threadsafe(loop.create_task, awaitable)


async def wrap_task_context(
    loop: asyncio.AbstractEventLoop,
    task_context: list[asyncio.Task[Any]],
    awaitable: Awaitable[_R],
) -> _R:
    if task_context is None:
        return await awaitable

    current_task = asyncio.current_task(loop)
    if current_task is None:
        return await awaitable

    task_context.append(current_task)
    try:
        return await awaitable
    finally:
        task_context.remove(current_task)


ExcInfo = Union[
    tuple[type[BaseException], BaseException, types.TracebackType],
    tuple[None, None, None],
]


class ThreadHandlerType(Protocol, Generic[_R]):
    def __call__(
        self,
        loop: asyncio.AbstractEventLoop,
        exc_info: ExcInfo,
        task_context: list[asyncio.Task[Any]],
        func: Callable[[Callable[[], _R]], _R],
        child: Callable[[], _R],
    ) -> _R:
        ...


async def run_in_executor(
    *,
    loop: asyncio.AbstractEventLoop,
    executor: concurrent.futures.ThreadPoolExecutor,
    thread_handler: ThreadHandlerType[_R],
    child: Callable[[], _R],
) -> _R:
    context = contextvars.copy_context()
    func = context.run
    task_context: list[asyncio.Task[Any]] = []

    # Run the code in the right thread
    exec_coro = loop.run_in_executor(
        executor,
        functools.partial(
            thread_handler,
            loop,
            sys.exc_info(),
            task_context,
            func,
            child,
        ),
    )
    ret: _R
    try:
        ret = await asyncio.shield(exec_coro)
    except asyncio.CancelledError:
        cancel_parent = True
        try:
            task = task_context[0]
            task.cancel()
            try:
                await task
                cancel_parent = False
            except asyncio.CancelledError:
                pass
        except IndexError:
            pass
        if exec_coro.done():
            raise
        if cancel_parent:
            exec_coro.cancel()
        ret = await exec_coro
    finally:
        _restore_context(context)

    return ret
