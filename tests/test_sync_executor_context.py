"""Show which executor each task sees before, during, and after a forced scope.

Run with ``python -m pytest -q -s tests/test_sync_executor_context.py`` to see
an ordered trace. No database is needed. Events control the order; no sleeps
are used. All tasks run on the same event loop and use normal task creation,
which copies the creator's context.
"""

import asyncio
import multiprocessing
import sys
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor

import pytest

from asgiref.current_thread_executor import CurrentThreadExecutor
from asgiref.sync import (
    AsyncToSync,
    SyncToAsync,
    ThreadSensitiveContext,
    async_to_sync,
    sync_to_async,
)


async def check_round_trip(
    expected_thread: threading.Thread,
    expected_executor: CurrentThreadExecutor | None,
    expected_context: ThreadSensitiveContext,
    during_callback: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Exercise both reads and writes of current through a sync/async round trip."""
    loop = asyncio.get_running_loop()
    assert AsyncToSync.executors.current is expected_executor
    assert SyncToAsync.thread_sensitive_context.get() is expected_context

    async def async_callback() -> None:
        assert asyncio.get_running_loop() is loop
        # AsyncToSync installs a new executor for this callback, not for siblings.
        callback_executor = AsyncToSync.executors.current
        assert isinstance(callback_executor, CurrentThreadExecutor)
        assert callback_executor is not expected_executor
        assert SyncToAsync.thread_sensitive_context.get() is expected_context
        if during_callback is not None:
            await during_callback()
            assert AsyncToSync.executors.current is callback_executor
        assert await sync_to_async(threading.current_thread)() is expected_thread
        assert AsyncToSync.executors.current is callback_executor

    def sync_caller() -> None:
        assert threading.current_thread() is expected_thread
        assert AsyncToSync.executors.current is expected_executor
        # AsyncToSync must be called from sync code, not the event-loop thread.
        async_to_sync(async_callback)()
        assert AsyncToSync.executors.current is expected_executor

    await sync_to_async(sync_caller)()
    assert AsyncToSync.executors.current is expected_executor
    assert SyncToAsync.thread_sensitive_context.get() is expected_context


async def sibling_task_created_before(
    parent_thread: threading.Thread,
    parent_executor: CurrentThreadExecutor,
    parent_context: ThreadSensitiveContext,
    *,
    events: dict[str, asyncio.Event],
) -> None:
    async def wait_for_forced_scope() -> None:
        print(
            "BEFORE: async callback started; its bridge executor is active.",
            flush=True,
        )
        events["before_started"].set()
        # Keep this bridge active while the other task clears current.
        await events["scope_entered"].wait()

    await check_round_trip(
        parent_thread, parent_executor, parent_context, wait_for_forced_scope
    )
    print(
        "BEFORE: callback and sibling kept their own executor bindings.",
        flush=True,
    )
    events["before_checked"].set()

    await events["scope_exited"].wait()
    assert AsyncToSync.executors.current is parent_executor
    assert SyncToAsync.thread_sensitive_context.get() is parent_context


async def sibling_task_created_after(
    parent_thread: threading.Thread,
    parent_executor: CurrentThreadExecutor,
    parent_context: ThreadSensitiveContext,
    *,
    events: dict[str, asyncio.Event],
) -> None:
    assert events["scope_entered"].is_set() and not events["scope_exited"].is_set()

    async def wait_for_isolated_check() -> None:
        print(
            "AFTER: async callback started while the forced scope is open.",
            flush=True,
        )
        events["after_bridge_entered"].set()
        # Let the isolated task read current while this executor is active.
        await events["after_bridge_checked"].wait()

    await check_round_trip(
        parent_thread, parent_executor, parent_context, wait_for_isolated_check
    )
    print(
        "AFTER: parent executor restored; sync work used the parent thread.",
        flush=True,
    )
    events["after_checked"].set()

    await events["scope_exited"].wait()
    assert AsyncToSync.executors.current is parent_executor
    assert SyncToAsync.thread_sensitive_context.get() is parent_context


async def task_with_forced_scope(
    parent_thread: threading.Thread,
    parent_executor: CurrentThreadExecutor,
    parent_context: ThreadSensitiveContext,
    *,
    events: dict[str, asyncio.Event],
) -> None:
    assert AsyncToSync.executors.current is parent_executor
    with ThreadPoolExecutor(max_workers=1) as executor:
        async with ThreadSensitiveContext(executor=executor) as child_context:
            # ty keeps the earlier non-None narrowing across __aenter__.
            # getattr reads the binding without reusing that narrowing.
            assert getattr(AsyncToSync.executors, "current") is None
            child_thread = await sync_to_async(threading.current_thread)()
            assert child_thread is not parent_thread
            print(
                "ISOLATED: current is None; sync work uses a new worker.",
                flush=True,
            )
            events["scope_entered"].set()
            await events["before_checked"].wait()

            async def child_created_inside() -> None:
                # Unlike siblings, this task inherits the forced scope.
                await check_round_trip(child_thread, None, child_context)
                print(
                    "INSIDE: inherits current=None and uses the isolated worker.",
                    flush=True,
                )

            await asyncio.create_task(child_created_inside(), name="inside")
            events["inside_checked"].set()
            await events["after_bridge_entered"].wait()
            assert getattr(AsyncToSync.executors, "current") is None
            assert SyncToAsync.thread_sensitive_context.get() is child_context
            assert await sync_to_async(threading.current_thread)() is child_thread
            print(
                "ISOLATED: current is still None while AFTER's executor is active.",
                flush=True,
            )
            events["after_bridge_checked"].set()
            await events["after_checked"].wait()
            assert getattr(AsyncToSync.executors, "current") is None

        assert AsyncToSync.executors.current is parent_executor
        assert SyncToAsync.thread_sensitive_context.get() is parent_context
        # The caller owns the executor, so the worker is still running.
        assert child_thread.is_alive()
        print("ISOLATED: parent executor restored; worker kept.", flush=True)
    assert not child_thread.is_alive()
    events["scope_exited"].set()


def run_executor_context_scenario() -> None:
    """Run a request with older and newer siblings, plus a child of the forced task.

    At the very end of this functiion, we call `async_to_sync`! This simulates
    the scenario where there is a parent thread (this thread) with a non-null
    executor setup.

    """
    # Spawn imports this module without pytest's assertion rewriting.
    if sys.flags.optimize:
        raise RuntimeError(
            "This example requires assertions. Disable -O, -OO, and PYTHONOPTIMIZE."
        )
    parent_thread = threading.current_thread()

    async def view() -> None:
        """Fake Django view"""
        parent_executor = AsyncToSync.executors.current
        assert isinstance(parent_executor, CurrentThreadExecutor)
        parent_context = SyncToAsync.thread_sensitive_context.get()

        # These `Event` objects are for signalling, to make a sequence of
        # action happen deterministically in a predicatable order.
        events = {
            "before_started": asyncio.Event(),
            "scope_entered": asyncio.Event(),
            "before_checked": asyncio.Event(),
            "inside_checked": asyncio.Event(),
            "after_bridge_entered": asyncio.Event(),
            "after_bridge_checked": asyncio.Event(),
            "after_checked": asyncio.Event(),
            "scope_exited": asyncio.Event(),
        }

        # The view creates both siblings. It never enters the forced scope.
        # TaskGroup also cancels the remaining tasks if an assertion fails.
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(
                sibling_task_created_before(
                    parent_thread, parent_executor, parent_context, events=events
                ),
                name="before",
            )
            await events["before_started"].wait()
            tasks.create_task(
                task_with_forced_scope(
                    parent_thread, parent_executor, parent_context, events=events
                ),
                name="isolated",
            )
            await events["inside_checked"].wait()
            assert AsyncToSync.executors.current is parent_executor
            assert SyncToAsync.thread_sensitive_context.get() is parent_context
            tasks.create_task(
                sibling_task_created_after(
                    parent_thread, parent_executor, parent_context, events=events
                ),
                name="after",
            )

        await check_round_trip(parent_thread, parent_executor, parent_context)
        print(
            "PARENT: executor and thread still work after all tasks finish.", flush=True
        )

    async def request() -> None:
        """Fake django request"""
        async with ThreadSensitiveContext():
            await view()

    # Give the request a real, non-None CurrentThreadExecutor to inherit.
    async_to_sync(request)()


def test_force_new_context_keeps_executor_bindings_local_to_each_task() -> None:
    """Clearing current in one task leaves both older and newer siblings unchanged.

    We're trying to validate that in the new code path in `ThreadSensitiveContext`
    when the new `executor` parameter is passed, our assignment of

    ```
    AsyncToSync.executors.current = None
    ```

    doesn't interfere with unrelated concurrent tasks operating within the
    same thread of the calling (async) context. The thinking behind the
    concern is "What if there are other async tasks in the caller environment
    that are also using `AsyncToSync.executors`?"

    Based on reading the code, it seems like perhaps the `AsyncToSync.executors.current`
    is a thread-local variable, so setting it to `None` in one task might affect
    other users in the same thread; however it is actually stored in a `Local`
    backed by a contextvar. By default, each new async task gets a copy of its
    creator's context, not a clone of the executor. `Local` also copies its stored
    dictionary when an attribute changes, so setting `current` doesn't change
    the binding in another task's copy of the context.

    So this test sets up an elaborate system to try to verify the desired
    behaviour.

    More formally:
    A child task created inside the forced scope inherits its context and uses
    the same worker. Each task can make sync/async calls without replacing
    another task's executor binding.

    We start a brand spanking new process to ensure a clean slate for these
    tests.

    """
    # Bound the whole example, including worker shutdown if a bridge deadlocks.
    process = multiprocessing.get_context("spawn").Process(
        target=run_executor_context_scenario
    )
    process.start()
    try:
        process.join(30)
        if process.is_alive():
            pytest.fail("executor context example deadlocked")
        # TaskGroup and the sync/async futures propagate assertion failures.
        # An unhandled failure gives the child a nonzero exit code.
        if process.exitcode != 0:
            pytest.fail(
                f"executor context example failed with exit code {process.exitcode}; "
                "see the child process traceback"
            )
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
        process.close()
