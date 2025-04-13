import asyncio
import contextvars
import functools
import sys
from typing import Any

import sniffio
import trio.lowlevel
import trio.to_thread

from . import _asyncio
from ._context import restore_context as _restore_context


class TrioThreadCancelled(BaseException):
    pass


def get_running_loop():
    try:
        asynclib = sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        return asyncio.get_running_loop()

    if asynclib == "asyncio":
        return asyncio.get_running_loop()
    if asynclib == "trio":
        return trio.lowlevel.current_token()
    raise RuntimeError(f"unsupported library {asynclib}")


@trio.lowlevel.disable_ki_protection
async def wrap_awaitable(awaitable):
    return await awaitable


def create_task_threadsafe(loop, awaitable):
    if isinstance(loop, trio.lowlevel.TrioToken):
        try:
            loop.run_sync_soon(
                trio.lowlevel.spawn_system_task,
                wrap_awaitable,
                awaitable,
            )
        except trio.RunFinishedError:
            raise RuntimeError("trio loop no-longer running")

    return _asyncio.create_task_threadsafe(loop, awaitable)


async def run_in_executor(*, loop, executor, thread_handler, child):
    if isinstance(loop, trio.lowlevel.TrioToken):
        context = contextvars.copy_context()
        func = context.run
        task_context: list[asyncio.Task[Any]] = []

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

                async def handle_cancel():
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
            else:
                event = trio.Event()

                def callback(fut):
                    loop.run_sync_soon(event.set)

                fut = executor.submit(full_func)
                fut.add_done_callback(callback)

                async def handle_cancel_fut():
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
        finally:
            _restore_context(context)

    return await _asyncio.run_in_executor(
        loop=loop, executor=executor, thread_handler=thread_handler, func=func
    )


async def wrap_task_context(loop, task_context, awaitable):
    if task_context is None:
        return await awaitable

    if isinstance(loop, trio.lowlevel.TrioToken):
        with trio.CancelScope() as scope:
            task_context.append(scope)
            try:
                return await awaitable
            finally:
                task_context.remove(scope)
        if scope.cancelled_caught:
            raise TrioThreadCancelled

    return await _asyncio.wrap_task_context(loop, task_context, awaitable)
