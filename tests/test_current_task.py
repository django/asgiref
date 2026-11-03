import asyncio
import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from asgiref.sync import async_to_sync, get_current_task, sync_to_async


def test_no_task_in_synchronous_code():
    assert get_current_task() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("thread_sensitive", [True, False])
@pytest.mark.parametrize("explicit_context", [True, False])
async def test_calling_task_identity(thread_sensitive, explicit_context):
    parent = asyncio.current_task()
    context = contextvars.copy_context() if explicit_context else None
    wrapped = sync_to_async(
        get_current_task, thread_sensitive=thread_sensitive, context=context
    )

    async def child():
        task = asyncio.current_task()
        assert task is not parent
        assert get_current_task() is task
        assert await wrapped() is task

    assert get_current_task() is parent
    assert await wrapped() is parent
    await asyncio.create_task(child())
    assert await wrapped() is parent


@pytest.mark.parametrize("fail", [True, False])
def test_nested_bridges_restore_task(fail):
    async def outer():
        parent = asyncio.current_task()

        async def inner():
            task = asyncio.current_task()
            assert task is not parent
            assert get_current_task() is task
            assert await sync_to_async(get_current_task)() is task
            if fail:
                raise ValueError("inner failed")

        def synchronous():
            assert get_current_task() is parent
            if fail:
                with pytest.raises(ValueError, match="inner failed"):
                    async_to_sync(inner)()
            else:
                async_to_sync(inner)()
            assert get_current_task() is parent

        await sync_to_async(synchronous)()
        assert get_current_task() is parent

    assert get_current_task() is None
    async_to_sync(outer)()
    assert get_current_task() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [True, False])
async def test_worker_does_not_retain_task(fail):
    task = asyncio.current_task()

    def synchronous():
        assert get_current_task() is task
        if fail:
            raise ValueError("sync failed")

    with ThreadPoolExecutor(max_workers=1) as executor:
        wrapped = sync_to_async(synchronous, thread_sensitive=False, executor=executor)
        if fail:
            with pytest.raises(ValueError, match="sync failed"):
                await wrapped()
        else:
            await wrapped()
        assert await asyncio.wrap_future(executor.submit(get_current_task)) is None


@pytest.mark.asyncio
async def test_cancelled_call_retains_identity_until_worker_finishes():
    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    identities = []

    def synchronous():
        identities.append(get_current_task())
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        identities.append(get_current_task())

    with ThreadPoolExecutor(max_workers=1) as executor:
        wrapped = sync_to_async(synchronous, thread_sensitive=False, executor=executor)
        task = asyncio.create_task(wrapped())
        try:
            await asyncio.wait_for(started.wait(), 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.wrap_future(executor.submit(get_current_task)) is None
    assert identities == [task, task]


@pytest.mark.asyncio
async def test_event_loop_callback_has_no_task():
    # A loop running inside the sync worker must not report the suspended
    # outer caller's identity in callbacks that are outside any task.
    async def inner():
        assert get_current_task() is asyncio.current_task()
        loop = asyncio.get_running_loop()
        result = loop.create_future()
        loop.call_soon(lambda: result.set_result(get_current_task()))
        assert await result is None

    def synchronous():
        parent = get_current_task()
        asyncio.run(inner())
        assert get_current_task() is parent

    await sync_to_async(synchronous)()
