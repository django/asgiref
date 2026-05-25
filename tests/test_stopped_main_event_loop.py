"""Regression test for #525 — AsyncToSync hangs when the captured
`main_event_loop` is stopped.

This issue is fixed in https://pypi.org/project/asgire/, the drop-in replacement for asgiref.

Bug: ``AsyncToSync.__call__`` falls back to a captured ``main_event_loop``
from ``SyncToAsync.threadlocal`` when the calling thread has no running
loop of its own. Before #528 nothing checked whether that captured loop
was still running. If it was stopped (typical between pytest-asyncio
tests, or any time a thread-pool worker outlives the loop that spawned
it), ``call_soon_threadsafe`` cheerfully queued a callback that the
stopped loop would never run, and ``current_executor.run_until_future``
then blocked forever.

This test plants a stopped loop on a worker thread's
``SyncToAsync.threadlocal``, then calls ``async_to_sync`` from that
worker thread. With the fix in place the call returns; without the fix
it hangs and the watchdog fails the test.

References:
    https://github.com/django/asgiref/issues/525
    https://github.com/django/asgiref/pull/528
"""

import asyncio
import os
import threading
import time

from asgiref.sync import SyncToAsync, async_to_sync

WATCHDOG_SECONDS = 5


def test_async_to_sync_does_not_hang_when_threadlocal_loop_is_stopped() -> None:
    # Daemon threads so a hung worker (when the bug fires) doesn't keep
    # the test process alive after pytest has reported the failure.
    barrier = threading.Event()
    state: dict = {"result": None, "error": None}

    def _worker() -> None:
        # Step 1: plant a stopped loop on this worker's threadlocal, the
        # way `SyncToAsync.thread_handler` does at the start of every
        # `sync_to_async` dispatch. The loop is freshly created and
        # never started, so `is_running()` is False.
        stale_loop = asyncio.new_event_loop()
        SyncToAsync.threadlocal.main_event_loop = stale_loop
        SyncToAsync.threadlocal.main_event_loop_pid = os.getpid()

        # Step 2: drive `async_to_sync`. The threadlocal fallback inside
        # `AsyncToSync.__call__` restores the stopped loop and schedules
        # the awaitable on it via `call_soon_threadsafe`. With the fix,
        # the stopped loop is rejected and a fresh loop is used instead;
        # without the fix, `run_until_future` blocks here forever.
        async def hello() -> str:
            return "hello"

        try:
            state["result"] = async_to_sync(hello)()
        except BaseException as exc:  # pragma: no cover - belt and braces
            state["error"] = exc
        finally:
            barrier.set()

    thread = threading.Thread(
        target=_worker, name="stale-loop-worker", daemon=True
    )
    start = time.perf_counter()
    thread.start()

    if not barrier.wait(timeout=WATCHDOG_SECONDS):
        elapsed = time.perf_counter() - start
        raise AssertionError(
            f"async_to_sync blocked for {elapsed:.1f}s waiting on a "
            "stopped main_event_loop captured via SyncToAsync.threadlocal "
            "— regression of #525"
        )

    if state["error"] is not None:
        raise state["error"]
    assert state["result"] == "hello"
