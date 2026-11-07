import asyncio

import pytest

from asgiref.testing import ApplicationCommunicator
from asgiref.wsgi import WsgiToAsgi


@pytest.mark.asyncio
async def test_receive_nothing():
    """
    Tests ApplicationCommunicator.receive_nothing to return the correct value.
    """

    # Get an ApplicationCommunicator instance
    def wsgi_application(environ, start_response):
        start_response("200 OK", [])
        yield b"content"

    application = WsgiToAsgi(wsgi_application)
    instance = ApplicationCommunicator(
        application,
        {
            "type": "http",
            "http_version": "1.0",
            "method": "GET",
            "path": "/foo/",
            "query_string": b"bar=baz",
            "headers": [],
        },
    )

    # No event
    assert await instance.receive_nothing() is True

    # Produce 3 events to receive
    await instance.send_input({"type": "http.request"})
    # Start event of the response
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    # First body event of the response announcing further body event
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    # Last body event of the response
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    # Response received completely
    assert await instance.receive_nothing(0.01) is True


@pytest.mark.asyncio
async def test_receive_output_timeout_restores_cancellation_count():
    """
    A handled timeout must not leave the calling task in a cancelling state.
    """

    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    task = asyncio.current_task()
    assert task is not None
    before = task.cancelling()

    try:
        with pytest.raises(TimeoutError):
            await instance.receive_output(timeout=0.01)
        assert task.cancelling() == before
    finally:
        while task.cancelling() > before:
            task.uncancel()


def test_receive_nothing_lazy_loop():
    """
    Tests ApplicationCommunicator.receive_nothing to return the correct value.
    """

    # Get an ApplicationCommunicator instance
    def wsgi_application(environ, start_response):
        start_response("200 OK", [])
        yield b"content"

    application = WsgiToAsgi(wsgi_application)
    instance = ApplicationCommunicator(
        application,
        {
            "type": "http",
            "http_version": "1.0",
            "method": "GET",
            "path": "/foo/",
            "query_string": b"bar=baz",
            "headers": [],
        },
    )

    async def test():
        # No event
        assert await instance.receive_nothing() is True

        # Produce 3 events to receive
        await instance.send_input({"type": "http.request"})
        # Start event of the response
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        # First body event of the response announcing further body event
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        # Last body event of the response
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        # Response received completely
        assert await instance.receive_nothing(0.01) is True

    asyncio.run(test())


@pytest.mark.asyncio
async def test_wait_outer_timeout_propagates():
    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(instance.wait(), timeout=0.01)


@pytest.mark.asyncio
async def test_wait_asyncio_timeout_propagates():
    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await instance.wait(timeout=10)


@pytest.mark.asyncio
async def test_wait_external_cancellation_propagates():
    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    task = asyncio.create_task(instance.wait())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_wait_application_cancellation_is_silent():
    async def application(scope, receive, send):
        raise asyncio.CancelledError

    instance = ApplicationCommunicator(application, {})
    assert await instance.wait() is None


@pytest.mark.asyncio
async def test_wait_own_timeout_is_silent():
    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    assert await instance.wait(timeout=0.01) is None


@pytest.mark.asyncio
async def test_wait_application_timeout_error_propagates():
    async def application(scope, receive, send):
        raise TimeoutError("application timeout")

    instance = ApplicationCommunicator(application, {})
    with pytest.raises(TimeoutError, match="application timeout"):
        await instance.wait()


@pytest.mark.asyncio
async def test_wait_invalid_timeout_cancels_application():
    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    with pytest.raises(TypeError):
        await instance.wait(timeout="bad")

    assert instance.future.done()
    assert instance.future.cancelled()
