import asyncio

import pytest

from asgiref.timeout import timeout


@pytest.mark.asyncio
async def test_timeout_uncancels_task_on_expiry():
    """
    When the timeout expires and swallows the CancelledError it raised,
    it should also uncancel() the task so the cancel it issued doesn't
    linger on the task's cancel count.
    """
    task = asyncio.current_task()
    assert task is not None
    cancelling_before = task.cancelling()

    with pytest.raises(asyncio.TimeoutError):
        async with timeout(0.01):
            await asyncio.sleep(1)

    assert task.cancelling() == cancelling_before


@pytest.mark.asyncio
async def test_timeout_does_not_uncancel_unrelated_cancellation():
    """
    If the block raises a CancelledError that isn't the one the timeout
    itself triggered, the CancelledError should propagate untouched and
    no uncancel() should happen.
    """
    task = asyncio.current_task()
    assert task is not None
    cancelling_before = task.cancelling()

    with pytest.raises(asyncio.CancelledError):
        async with timeout(10):
            raise asyncio.CancelledError

    assert task.cancelling() == cancelling_before
