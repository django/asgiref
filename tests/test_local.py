import asyncio
import threading

import pytest

from asgiref.local import Local
from asgiref.sync import sync_to_async


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
    print("outside ID", Local._get_context_id())
    # Assign and check it does not persist inside the thread
    class TestThread(threading.Thread):
        # Failure reason
        failed = "unknown"

        def run(self):
            print("inside ID", Local._get_context_id())
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


@pytest.mark.asyncio
async def test_local_cleanup():
    """
    Tests that local cleans up dead threads and tasks
    """
    # Set up the local
    test_local = Local()
    # Assign in a thread
    class TestThread(threading.Thread):
        def run(self):
            test_local.foo = 456

    thread = TestThread()
    thread.start()
    thread.join()
    # Assign in a Task
    async def test_task():
        test_local.foo = 456

    test_future = asyncio.ensure_future(test_task())
    await test_future
    # Check there are two things in the storage
    assert len(test_local._storage) == 2
    # Force cleanup
    test_local._last_cleanup = 0
    test_local.foo = 1
    # There should now only be one thing (this task) in the storage
    assert len(test_local._storage) == 1
