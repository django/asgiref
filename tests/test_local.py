import asyncio
import gc
import threading
from threading import Thread

import pytest

from asgiref.local import Local
from asgiref.sync import async_to_sync, sync_to_async


@pytest.mark.asyncio
async def test_local_task():
    """
    Tests that local works just inside a normal task context
    """

    test_local = Local()
    # Unassigned should be an error
    with pytest.raises(AttributeError):
        test_local.foo
    # Assign and check it persists
    test_local.foo = 1
    assert test_local.foo == 1
    # Delete and check it errors again
    del test_local.foo
    with pytest.raises(AttributeError):
        test_local.foo


def test_local_thread():
    """
    Tests that local works just inside a normal thread context
    """

    test_local = Local()
    # Unassigned should be an error
    with pytest.raises(AttributeError):
        test_local.foo
    # Assign and check it persists
    test_local.foo = 2
    assert test_local.foo == 2
    # Delete and check it errors again
    del test_local.foo
    with pytest.raises(AttributeError):
        test_local.foo


def test_local_thread_nested():
    """
    Tests that local does not leak across threads
    """

    test_local = Local()
    # Unassigned should be an error
    with pytest.raises(AttributeError):
        test_local.foo

    # Assign and check it does not persist inside the thread
    class TestThread(threading.Thread):
        # Failure reason
        failed = "unknown"

        def run(self):
            # Make sure the attribute is not there
            try:
                test_local.foo
                self.failed = "leak inside"
                return
            except AttributeError:
                pass
            # Check the value is good
            self.failed = "set inside"
            test_local.foo = 123
            assert test_local.foo == 123
            # Binary signal that these tests passed to the outer thread
            self.failed = ""

    test_local.foo = 8
    thread = TestThread()
    thread.start()
    thread.join()
    assert thread.failed == ""
    # Check it didn't leak back out
    assert test_local.foo == 8


def test_local_cycle():
    """
    Tests that Local can handle cleanup up a cycle to itself
    (Borrowed and modified from the CPython threadlocal tests)
    """

    locals = None
    matched = 0
    e1 = threading.Event()
    e2 = threading.Event()

    def f():
        nonlocal matched
        # Involve Local in a cycle
        cycle = [Local()]
        cycle.append(cycle)
        cycle[0].foo = "bar"

        # GC the cycle
        del cycle
        gc.collect()

        # Trigger the local creation outside
        e1.set()
        e2.wait()

        # New Locals should be empty
        matched = len(
            [local for local in locals if getattr(local, "foo", None) == "bar"]
        )

    t = threading.Thread(target=f)
    t.start()
    e1.wait()
    # Creates locals outside of the inner thread
    locals = [Local() for i in range(100)]
    e2.set()
    t.join()

    assert matched == 0


@pytest.mark.asyncio
async def test_local_task_to_sync():
    """
    Tests that local carries through sync_to_async
    """
    # Set up the local
    test_local = Local()
    test_local.foo = 3

    # Look at it in a sync context
    def sync_function():
        assert test_local.foo == 3
        test_local.foo = "phew, done"

    await sync_to_async(sync_function)()
    # Check the value passed out again
    assert test_local.foo == "phew, done"


def test_local_thread_to_async():
    """
    Tests that local carries through async_to_sync
    """
    # Set up the local
    test_local = Local()
    test_local.foo = 12

    # Look at it in an async context
    async def async_function():
        assert test_local.foo == 12
        test_local.foo = "inside"

    async_to_sync(async_function)()
    # Check the value passed out again
    assert test_local.foo == "inside"


@pytest.mark.asyncio
async def test_local_task_to_sync_to_task():
    """
    Tests that local carries through sync_to_async and then back through
    async_to_sync
    """
    # Set up the local
    test_local = Local()
    test_local.foo = 756

    # Look at it in an async context inside a sync context
    def sync_function():
        async def async_function():
            assert test_local.foo == 756
            test_local.foo = "dragons"

        async_to_sync(async_function)()

    await sync_to_async(sync_function)()
    # Check the value passed out again
    assert test_local.foo == "dragons"


@pytest.mark.asyncio
async def test_local_many_layers():
    """
    Tests that local carries through a lot of layers of sync/async
    """
    # Set up the local
    test_local = Local()
    test_local.foo = 8374

    # Make sure we go between each world at least twice
    def sync_function():
        async def async_function():
            def sync_function_2():
                async def async_function_2():
                    assert test_local.foo == 8374
                    test_local.foo = "miracles"

                async_to_sync(async_function_2)()

            await sync_to_async(sync_function_2)()

        async_to_sync(async_function)()

    await sync_to_async(sync_function)()
    # Check the value passed out again
    assert test_local.foo == "miracles"


@pytest.mark.asyncio
async def test_local_critical_no_task_to_thread():
    """
    Tests that local doesn't go through sync_to_async when the local is set
    as thread-critical.
    """
    # Set up the local
    test_local = Local(thread_critical=True)
    test_local.foo = 86

    # Look at it in a sync context
    def sync_function():
        with pytest.raises(AttributeError):
            test_local.foo
        test_local.foo = "secret"
        assert test_local.foo == "secret"

    await sync_to_async(sync_function)()
    # Check the value outside is not touched
    assert test_local.foo == 86


def test_local_critical_no_thread_to_task():
    """
    Tests that local does not go through async_to_sync when the local is set
    as thread-critical
    """
    # Set up the local
    test_local = Local(thread_critical=True)
    test_local.foo = 89

    # Look at it in an async context
    async def async_function():
        with pytest.raises(AttributeError):
            test_local.foo
        test_local.foo = "numbers"
        assert test_local.foo == "numbers"

    async_to_sync(async_function)()
    # Check the value outside
    assert test_local.foo == 89


@pytest.mark.asyncio
async def test_local_threads_and_tasks():
    """
    Tests that local and threads don't interfere with each other.
    """

    test_local = Local()
    test_local.counter = 0

    def sync_function(expected):
        assert test_local.counter == expected
        test_local.counter += 1

    async def async_function(expected):
        assert test_local.counter == expected
        test_local.counter += 1

    await sync_to_async(sync_function)(0)
    assert test_local.counter == 1

    await async_function(1)
    assert test_local.counter == 2

    class TestThread(threading.Thread):
        def run(self):
            with pytest.raises(AttributeError):
                test_local.counter
            test_local.counter = -1

    await sync_to_async(sync_function)(2)
    assert test_local.counter == 3

    threads = [TestThread() for _ in range(5)]
    for thread in threads:
        thread.start()

    threads[0].join()

    await sync_to_async(sync_function)(3)
    assert test_local.counter == 4

    await async_function(4)
    assert test_local.counter == 5

    for thread in threads[1:]:
        thread.join()

    await sync_to_async(sync_function)(5)
    assert test_local.counter == 6


def test_thread_critical_local_not_context_dependent_in_sync_thread():
    # Test function is sync, thread critical local should
    # be visible everywhere in the sync thread, even if set
    # from inside a sync_to_async/async_to_sync stack (so
    # long as it was set in sync code)
    test_local_tc = Local(thread_critical=True)
    test_local_not_tc = Local(thread_critical=False)
    test_thread = threading.current_thread()

    @sync_to_async
    def inner_sync_function():
        # sync_to_async should run this code inside the original
        # sync thread, confirm this here
        assert test_thread == threading.current_thread()
        test_local_tc.test_value = "_123_"
        test_local_not_tc.test_value = "_456_"

    @async_to_sync
    async def async_function():
        await asyncio.create_task(inner_sync_function())

    async_function()

    # assert: the inner_sync_function should have set a value
    # visible here
    assert test_local_tc.test_value == "_123_"
    # however, if the local was non-thread-critical, then the
    # inner value was set inside a new async context, meaning that
    # we do not see it, as context vars don't propagate up the stack
    assert not hasattr(test_local_not_tc, "test_value")


def test_visibility_thread_asgiref() -> None:
    """Check visibility with subthreads."""
    test_local = Local()
    test_local.value = 0

    def _test() -> None:
        # Local() is cleared when changing thread
        assert not hasattr(test_local, "value")
        setattr(test_local, "value", 1)
        assert test_local.value == 1

    thread = Thread(target=_test)
    thread.start()
    thread.join()

    assert test_local.value == 0


@pytest.mark.asyncio
async def test_visibility_task() -> None:
    """Check visibility with asyncio tasks."""
    test_local = Local()
    test_local.value = 0

    async def _test() -> None:
        # Local is inherited when changing task
        assert test_local.value == 0
        test_local.value = 1
        assert test_local.value == 1

    await asyncio.create_task(_test())

    # Changes should not leak to the caller
    assert test_local.value == 0
