__all__ = [
    "get_running_loop",
    "create_task_threadsafe",
    "wrap_task_context",
    "run_in_executor",
]

import asyncio
import contextvars
import functools
import sys
from asyncio import get_running_loop
from collections.abc import Callable
from typing import Any, TypeVar

from ._context import restore_context as _restore_context

_R = TypeVar("_R")


def create_task_threadsafe(loop, awaitable) -> None:
    loop.call_soon_threadsafe(loop.create_task, awaitable)


async def wrap_task_context(loop, task_context, awaitable):
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


async def run_in_executor(
    *, loop, executor, thread_handler, child: Callable[[], _R]
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
