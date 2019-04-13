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
        test_local.foo == 1
    # Assign and check it persists
    test_local.foo = 1
    assert test_local.foo == 1
    # Delete and check it errors again
    del test_local.foo
    with pytest.raises(AttributeError):
        test_local.foo == 1


def test_local_thread():
    """
    Tests that local works just inside a normal thread context
    """

    test_local = Local()
    # Unassigned should be an error
    with pytest.raises(AttributeError):
        test_local.foo == 2
    # Assign and check it persists
    test_local.foo = 2
    assert test_local.foo == 2
    # Delete and check it errors again
    del test_local.foo
    with pytest.raises(AttributeError):
        test_local.foo == 2


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
