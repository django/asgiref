import asyncio
import contextvars
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from asgiref.local import Local
from asgiref.sync import (
    AsyncToSync,
    SyncToAsync,
    ThreadSensitiveContext,
    async_to_sync,
    sync_to_async,
)


def single_worker() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1)


@pytest.mark.asyncio
async def test_executor_context_restores_parent() -> None:
    """Nested executor contexts use their executors and restore the parent on exit.

    The executors are not shut down on exit.
    """
    thread = sync_to_async(threading.current_thread)

    with single_worker() as child_executor, single_worker() as grandchild_executor:
        async with ThreadSensitiveContext() as parent:
            parent_thread = await thread()
            async with ThreadSensitiveContext(executor=child_executor) as child:
                child_thread = await thread()
                assert child_thread is not parent_thread
                assert await thread() is child_thread
                async with ThreadSensitiveContext():
                    assert await thread() is child_thread
                assert SyncToAsync.thread_sensitive_context.get() is child

                async with ThreadSensitiveContext(
                    executor=grandchild_executor
                ) as grandchild:
                    grandchild_thread = await thread()
                    assert grandchild_thread not in (parent_thread, child_thread)
                assert grandchild not in SyncToAsync.context_to_thread_executor
                assert grandchild_thread.is_alive()
                assert await thread() is child_thread

            assert child not in SyncToAsync.context_to_thread_executor
            assert child_thread.is_alive()
            assert SyncToAsync.thread_sensitive_context.get() is parent
            assert await thread() is parent_thread

    assert not child_thread.is_alive()
    assert not grandchild_thread.is_alive()


@pytest.mark.asyncio
async def test_executor_context_without_parent() -> None:
    """An executor context works without an outer context.

    Later calls use the default worker again.
    """
    thread = sync_to_async(threading.current_thread)
    parent_thread = await thread()
    with single_worker() as executor:
        async with ThreadSensitiveContext(executor=executor) as child:
            child_thread = await thread()
            assert child_thread is not parent_thread
        assert child not in SyncToAsync.context_to_thread_executor
        assert SyncToAsync.thread_sensitive_context.get(None) is None
        assert await thread() is parent_thread


@pytest.mark.asyncio
async def test_executor_context_reuses_executor() -> None:
    """Contexts that use the same executor, one after another, share its thread.

    Thread-bound data, such as a database connection, stays on that thread.
    """
    connections = Local(thread_critical=True)

    @sync_to_async
    def connection() -> tuple[threading.Thread, Any]:
        if not hasattr(connections, "default"):
            connections.default = object()
        return threading.current_thread(), connections.default

    with single_worker() as executor:
        async with ThreadSensitiveContext(executor=executor):
            first = await connection()
        async with ThreadSensitiveContext(executor=executor):
            assert await connection() == first
        assert await connection() != first


@pytest.mark.asyncio
async def test_executor_context_siblings_are_isolated() -> None:
    """Concurrent contexts with different executors use different threads.

    Each context keeps its thread, including for tasks created inside it.
    """
    thread = sync_to_async(threading.current_thread)
    both_inside = asyncio.Barrier(2)

    async def sibling() -> threading.Thread:
        with single_worker() as executor:
            async with ThreadSensitiveContext(executor=executor):
                first = await thread()
                await both_inside.wait()
                # Tasks inherit the context unless they explicitly create another.
                assert await asyncio.create_task(thread()) is first
                return first

    async with ThreadSensitiveContext():
        parent_thread = await thread()
        first, second = await asyncio.wait_for(
            asyncio.gather(sibling(), sibling()), timeout=5
        )
        assert first is not second
        assert parent_thread not in (first, second)
        assert await thread() is parent_thread


def executor_context_across_bridges(async_outermost: bool) -> None:
    thread = sync_to_async(threading.current_thread)

    async def inner_async(expected: threading.Thread) -> None:
        assert await thread() is expected
        assert await asyncio.create_task(thread()) is expected
        with single_worker() as executor:
            async with ThreadSensitiveContext(executor=executor):
                other = await thread()
                assert other is not expected
        assert await thread() is expected

    def inner_sync() -> threading.Thread:
        current = threading.current_thread()
        async_to_sync(inner_async)(current)
        return current

    async def outer_async(parent_thread: threading.Thread) -> None:
        parent_executor = AsyncToSync.executors.current
        assert await thread() is parent_thread
        with single_worker() as executor:
            async with ThreadSensitiveContext(executor=executor):
                child_thread = await thread()
                assert child_thread is not parent_thread
                assert await sync_to_async(inner_sync)() is child_thread
        assert AsyncToSync.executors.current is parent_executor
        assert await thread() is parent_thread

    def outer_sync() -> None:
        async_to_sync(outer_async)(threading.current_thread())

    if async_outermost:
        asyncio.run(sync_to_async(outer_sync)())
    else:
        outer_sync()


@pytest.mark.parametrize("async_outermost", [False, True])
def test_executor_context_across_bridges(async_outermost: bool) -> None:
    """Nested sync and async calls stay on the current context's worker.

    Executor contexts use their worker and restore the parent without
    deadlocking, whether the outermost caller is sync or async.
    """
    # A deadlocked worker can also block interpreter shutdown. Run the bridge
    # checks in a separate process so the parent can stop it after a timeout.
    # Spawn avoids inheriting executor state from the parent's worker threads.
    process = multiprocessing.get_context("spawn").Process(
        target=executor_context_across_bridges, args=(async_outermost,)
    )
    process.start()
    try:
        process.join(30)
        if process.is_alive():
            pytest.fail("thread-sensitive context deadlocked across sync/async bridges")
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
        process.close()


@pytest.mark.asyncio
async def test_executor_context_isolates_thread_critical_storage() -> None:
    """Executor contexts separate thread-bound data, such as database connections.

    Other context data still passes between the async caller and sync worker.
    """
    # Django's ConnectionHandler uses this storage for database wrappers.
    connections = Local(thread_critical=True)
    shared = Local()
    value: contextvars.ContextVar[str] = contextvars.ContextVar("value")
    shared.value = "parent"
    value.set("parent")

    @sync_to_async
    def connection() -> Any:
        if not hasattr(connections, "default"):
            connections.default = object()
        return connections.default

    @sync_to_async
    def update_context() -> None:
        assert shared.value == "parent"
        assert value.get() == "parent"
        shared.value = "child"
        value.set("child")

    with single_worker() as executor:
        async with ThreadSensitiveContext():
            parent = await connection()
            async with ThreadSensitiveContext(executor=executor):
                child = await connection()
                assert child is not parent
                assert await connection() is child
                await update_context()
            assert await connection() is parent
            assert shared.value == "child"
            assert value.get() == "child"


@pytest.mark.parametrize("error", [ValueError, asyncio.CancelledError])
def test_executor_context_restores_parent_on_error(
    error: type[BaseException],
) -> None:
    """An exception or cancellation restores the parent and keeps the executor."""

    async def run() -> None:
        parent_executor = AsyncToSync.executors.current
        with single_worker() as executor:
            async with ThreadSensitiveContext() as parent:
                parent_thread = await sync_to_async(threading.current_thread)()
                with pytest.raises(error):
                    async with ThreadSensitiveContext(executor=executor) as child:
                        child_thread = await sync_to_async(threading.current_thread)()
                        raise error()
                assert SyncToAsync.thread_sensitive_context.get() is parent
                assert AsyncToSync.executors.current is parent_executor
                assert child not in SyncToAsync.context_to_thread_executor
                assert await sync_to_async(threading.current_thread)() is parent_thread
            assert executor.submit(threading.current_thread).result() is child_thread

    async_to_sync(run)()


@pytest.mark.asyncio
async def test_executor_context_cancellation_does_not_wait_for_worker() -> None:
    """Cancellation exits the context while the worker finishes the call.

    The executor stays usable afterwards.
    """
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()
    threads = []

    def blocking() -> None:
        threads.append(threading.current_thread())
        loop.call_soon_threadsafe(started.set)
        release.wait(5)

    with single_worker() as executor:
        async with ThreadSensitiveContext() as parent:
            child = ThreadSensitiveContext(executor=executor)

            async def run() -> None:
                try:
                    async with child:
                        await sync_to_async(blocking)()
                finally:
                    assert SyncToAsync.thread_sensitive_context.get() is parent

            task = asyncio.create_task(run())
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=5)
                # The context exited while the worker is still busy.
                assert not release.is_set()
            finally:
                release.set()
                await asyncio.gather(task, return_exceptions=True)

            assert child not in SyncToAsync.context_to_thread_executor
            future = executor.submit(threading.current_thread)
            assert await asyncio.wrap_future(future) is threads[0]


@pytest.mark.asyncio
async def test_executor_context_leaves_non_thread_sensitive_calls_unchanged() -> None:
    """Calls with thread_sensitive=False keep using their chosen executor."""
    with single_worker() as other, single_worker() as executor:
        thread = sync_to_async(
            threading.current_thread, thread_sensitive=False, executor=other
        )
        expected = await thread()
        async with ThreadSensitiveContext(executor=executor):
            assert await thread() is expected
            assert await sync_to_async(threading.current_thread)() is not expected


@pytest.mark.asyncio
async def test_executor_context_reuse() -> None:
    """An executor context can be reused after exit, but not while it is active."""
    with single_worker() as executor:
        context = ThreadSensitiveContext(executor=executor)
        async with context:
            first = await sync_to_async(threading.current_thread)()
            with pytest.raises(RuntimeError, match="already entered"):
                async with context:
                    pass
        async with context:
            assert await sync_to_async(threading.current_thread)() is first


@pytest.mark.asyncio
async def test_executor_context_without_sync_work() -> None:
    """An unused executor context exits cleanly and restores the parent context."""
    with single_worker() as executor:
        async with ThreadSensitiveContext() as parent:
            async with ThreadSensitiveContext(executor=executor) as child:
                assert SyncToAsync.thread_sensitive_context.get() is child
            assert SyncToAsync.thread_sensitive_context.get() is parent
            assert child not in SyncToAsync.context_to_thread_executor
