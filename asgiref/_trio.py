import asyncio
import concurrent.futures
import contextvars
import functools
import sys
import types
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Generic, Protocol, TypeVar, Union

import sniffio
import trio.lowlevel
import trio.to_thread

from . import _asyncio
from ._context import restore_context as _restore_context

_R = TypeVar("_R")

Coro = Coroutine[Any, Any, _R]

Loop = Union[asyncio.AbstractEventLoop, trio.lowlevel.TrioToken]
TaskContext = list[Any]


class TrioThreadCancelled(BaseException):
    pass


def get_running_loop() -> Loop:

    try:
        asynclib = sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        return asyncio.get_running_loop()

    if asynclib == "asyncio":
        return asyncio.get_running_loop()
    if asynclib == "trio":
        return trio.lowlevel.current_trio_token()
    raise RuntimeError(f"unsupported library {asynclib}")


@trio.lowlevel.disable_ki_protection
async def wrap_awaitable(awaitable: Awaitable[_R]) -> _R:
    return await awaitable


def create_task_threadsafe(loop: Loop, awaitable: Coro[_R]) -> None:
    if isinstance(loop, trio.lowlevel.TrioToken):
        try:
            loop.run_sync_soon(
                trio.lowlevel.spawn_system_task,
                wrap_awaitable,
                awaitable,
            )
        except trio.RunFinishedError:
            raise RuntimeError("trio loop no-longer running")
        return

    _asyncio.create_task_threadsafe(loop, awaitable)


ExcInfo = Union[
    tuple[type[BaseException], BaseException, types.TracebackType],
    tuple[None, None, None],
]


class ThreadHandlerType(Protocol, Generic[_R]):
    def __call__(
        self,
        loop: Loop,
        exc_info: ExcInfo,
        task_context: TaskContext,
        func: Callable[[Callable[[], _R]], _R],
        child: Callable[[], _R],
    ) -> _R:
        ...


async def run_in_executor(
    *,
    loop: Loop,
    executor: concurrent.futures.ThreadPoolExecutor,
    thread_handler: ThreadHandlerType[_R],
    child: Callable[[], _R],
) -> _R:
    if isinstance(loop, trio.lowlevel.TrioToken):
        context = contextvars.copy_context()
        func = context.run
        task_context: TaskContext = []

        # Run the code in the right thread
        full_func = functools.partial(
            thread_handler,
            loop,
            sys.exc_info(),
            task_context,
            func,
            child,
        )
        try:
            if executor is None:

                async def handle_cancel() -> None:
                    try:
                        await trio.sleep_forever()
                    except trio.Cancelled:
                        if task_context:
                            task_context[0].cancel()
                        raise

                async with trio.open_nursery() as nursery:
                    nursery.start_soon(handle_cancel)
                    try:
                        return await trio.to_thread.run_sync(
                            thread_handler, func, abandon_on_cancel=False
                        )
                    except TrioThreadCancelled:
                        pass
                    finally:
                        nursery.cancel_scope.cancel()
                assert False
            else:
                event = trio.Event()

                def callback(fut: object) -> None:
                    loop.run_sync_soon(event.set)

                fut = executor.submit(full_func)
                fut.add_done_callback(callback)

                async def handle_cancel_fut() -> None:
                    try:
                        await trio.sleep_forever()
                    except trio.Cancelled:
                        fut.cancel()
                        if task_context:
                            task_context[0].cancel()
                        raise

                async with trio.open_nursery() as nursery:
                    nursery.start_soon(handle_cancel_fut)
                    with trio.CancelScope(shield=True):
                        await event.wait()
                        nursery.cancel_scope.cancel()
                        try:
                            return fut.result()
                        except TrioThreadCancelled:
                            pass
                assert False
        finally:
            _restore_context(context)

    else:
        return await _asyncio.run_in_executor(
            loop=loop, executor=executor, thread_handler=thread_handler, child=child
        )


async def wrap_task_context(
    loop: Loop, task_context: Union[TaskContext, None], awaitable: Awaitable[_R]
) -> _R:
    if task_context is None:
        return await awaitable

    if isinstance(loop, trio.lowlevel.TrioToken):
        with trio.CancelScope() as scope:
            task_context.append(scope)
            try:
                return await awaitable
            finally:
                task_context.remove(scope)
        raise TrioThreadCancelled

    return await _asyncio.wrap_task_context(loop, task_context, awaitable)
